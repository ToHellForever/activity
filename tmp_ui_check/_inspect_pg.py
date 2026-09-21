import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "activity.settings")
django.setup()

from django.db import connection  # noqa: E402

with connection.cursor() as cur:
    print("DB:", connection.settings_dict["ENGINE"], connection.settings_dict["NAME"])

    cur.execute(
        """
        SELECT conname, conrelid::regclass AS table_name,
               confrelid::regclass AS ref_table, confdeltype
        FROM pg_constraint
        WHERE confrelid = 'core_customuser'::regclass
        ORDER BY conname
        """
    )
    print("\n== FK constraints referencing core_customuser ==")
    for row in cur.fetchall():
        print(row)

    cur.execute(
        """
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public' AND table_name LIKE '%consent%'
        """
    )
    consent_tables = [r[0] for r in cur.fetchall()]
    print("\n== tables like %consent% ==", consent_tables)

    for t in consent_tables:
        cur.execute(f'SELECT COUNT(*) FROM "{t}"')
        print(f"\n-- {t}: rows={cur.fetchone()[0]}")
        cur.execute(
            """
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_name = %s ORDER BY ordinal_position
            """,
            [t],
        )
        for row in cur.fetchall():
            print("   ", row)

    cur.execute("SELECT id, email, first_name, last_name, is_active FROM core_customuser WHERE id = 62")
    print("\n== user 62 ==", cur.fetchall())

    cur.execute("SELECT MAX(id) FROM django_migrations WHERE app = 'core'")
    print("\nmax migration id core:", cur.fetchone())
    cur.execute("SELECT name FROM django_migrations WHERE app='core' ORDER BY id DESC LIMIT 5")
    print("last core migrations applied:", [r[0] for r in cur.fetchall()])
