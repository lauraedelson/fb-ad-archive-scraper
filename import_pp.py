import psycopg2
import ast
import sys
import psycopg2.extras
import configparser
import csv

csv.field_size_limit(sys.maxsize)

config = configparser.ConfigParser()
config.read(sys.argv[1])

#setup our db cursor
HOST = config['POSTGRES']['HOST']
DBNAME = config['POSTGRES']['DBNAME']
USER = config['POSTGRES']['USER']
PASSWORD = config['POSTGRES']['PASSWORD']
PORT = config['POSTGRES']['PORT']
PP_FILE = config['PP']['FILE']
DBAuthorize = "host=%s dbname=%s user=%s password=%s port=%s" % (HOST, DBNAME, USER, PASSWORD, PORT)
connection = psycopg2.connect(DBAuthorize)
cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)

ad_link_insert = 'insert into propublica(ad_id, political_prob, listbuilding_prob) VALUES '
targeting_insert = 'insert into propublica_targetings(ad_id, target_category, targeting) VALUES '
pp_trunc = 'truncate propublica'
pp_targeting_trunc = 'truncate propulbica_targeting'
ad_count = 0
with open(PP_FILE) as input:
    cursor.execute(pp_trunc)
    cursor.execute(pp_targeting_trunc)
    csv_reader = csv.DictReader(input)
    for parts in csv_reader:
        ad_id = parts['id']
        p_prob = parts['political_probability']
        l_prob = parts['listbuilding_fundraising_proba']
        if 'targets' in parts and parts['targets']:
            targetings = ast.literal_eval(parts['targets'])
            ad_link_insert += cursor.mogrify('(%s,%s,%s),', (ad_id, p_prob, l_prob)).decode('utf-8')
            for target in targetings:
                #print(target)
                #print(type(target))
                target_cat = target['target']
                targeting = ''
                if 'segment' in target:
                    targeting = target['segment']
                targeting_insert += cursor.mogrify('(%s,%s,%s),', (ad_id, target_cat, targeting)).decode('utf-8')
        ad_count += 1

        if ad_count >= 250:
            ad_link_insert = ad_link_insert[:-1]
            ad_link_insert += ';'
            targeting_insert = targeting_insert[:-1]
            targeting_insert += ';'
            print(cursor.mogrify(ad_link_insert))
            cursor.execute(ad_link_insert)
            print(cursor.mogrify(targeting_insert))
            cursor.execute(targeting_insert)
            ad_link_insert = 'insert into propublica(ad_id, political_prob, listbuilding_prob) VALUES '
            targeting_insert = 'insert into propublica_targetings(ad_id, target_category, targeting) VALUES '
            ad_count = 0

    if ad_count > 0:
        ad_link_insert = ad_link_insert[:-1]
        ad_link_insert += ';'
        print(cursor.mogrify(ad_link_insert))
        cursor.execute(ad_link_insert)
        targeting_insert = targeting_insert[:-1]
        targeting_insert += ';'
        print(cursor.mogrify(targeting_insert))
        cursor.execute(targeting_insert)

connection.commit()
connection.close
