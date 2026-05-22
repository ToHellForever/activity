import psycopg2

conn = psycopg2.connect(
    dbname="activity_db",
    user="postgres",
    password="Dima228anosov",
    host="localhost",
    port="5432"
)

cursor = conn.cursor()
cursor.execute("SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'core_order';")
rows = cursor.fetchall()

with open('table_structure.txt', 'w', encoding='utf-8') as f:
    for row in rows:
        f.write(f"{row[0]}: {row[1]}\n")

cursor.close()
conn.close()