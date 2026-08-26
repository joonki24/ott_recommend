import os
import psycopg
from dotenv import load_dotenv

load_dotenv()
conn = psycopg.connect(
    host='localhost',
    port=int(os.environ.get('PGPORT', 5432)),
    dbname='ott_recommend',
    user='postgres',
    password=os.environ['PGPASSWORD']
)
rows = conn.execute('SELECT person_name FROM person LIMIT 5').fetchall()
for r in rows:
    print(r[0])