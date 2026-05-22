import psycopg2
import os
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

conn = psycopg2.connect(
    dbname=os.getenv("DB_NAME", "activity"),
    user=os.getenv("DB_USER", "postgres"),
    password=os.getenv("DB_PASSWORD", "Dima228anosov"),
    host=os.getenv("DB_HOST", "localhost"),
    port=os.getenv("DB_PORT", "5432")
)

cursor = conn.cursor()
cursor.execute("SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'core_order';")
rows = cursor.fetchall()

print("Структура таблицы core_order:")
for row in rows:
    print(f"{row[0]}: {row[1]}")

cursor.close()
conn.close()
