import os
os.environ['DJANGO_SETTINGS_MODULE'] = 'activity.settings'
import django
django.setup()

from django.db import connection
cursor = connection.cursor()
cursor.execute("""
    SELECT column_name, is_nullable, column_default 
    FROM information_schema.columns 
    WHERE table_name='core_event' AND column_name='requires_strict_moderation'
""")
print(cursor.fetchall())
