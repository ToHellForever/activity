import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "activity.settings")
django.setup()

from django.db import connection

cur = connection.cursor()
cur.execute("select column_name from information_schema.columns where table_name='core_customuser'")
print("main db columns:", [r[0] for r in cur.fetchall()])

conn2 = connection
conn2.close()
from django.db import connections
import psycopg2
from django.conf import settings
c = psycopg2.connect(
    dbname="test_activity_db",
    user=settings.DATABASES["default"]["USER"],
    password=settings.DATABASES["default"].get("PASSWORD"),
    host=settings.DATABASES["default"].get("HOST", "localhost"),
    port=settings.DATABASES["default"].get("PORT", 5432),
)
c2 = c.cursor()
c2.execute("select column_name from information_schema.columns where table_name='core_customuser'")
print("test db columns:", [r[0] for r in c2.fetchall()])
c2.execute("select app, name from django_migrations where app='core' order by id")
print("applied core migrations:", [r[1] for r in c2.fetchall()])
c.close()

