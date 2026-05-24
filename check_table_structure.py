import psycopg2
from django.conf import settings

# Подключение к базе данных
conn = psycopg2.connect(
    dbname=settings.DATABASES['default']['NAME'],
    user=settings.DATABASES['default']['USER'],
    password=settings.DATABASES['default']['PASSWORD'],
    host=settings.DATABASES['default']['HOST'],
    port=settings.DATABASES['default']['PORT']
)

cursor = conn.cursor()

# Получение информации о столбцах таблицы core_order
cursor.execute("""
    SELECT column_name, data_type
    FROM information_schema.columns
    WHERE table_name = 'core_order';
""")

columns = cursor.fetchall()
print("Столбцы таблицы core_order:")
for column in columns:
    print(f"- {column[0]} ({column[1]})")

cursor.close()
conn.close()