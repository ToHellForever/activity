import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import django  # noqa: E402

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "activity.settings")
django.setup()

from django.db import connection  # noqa: E402

with connection.cursor() as cur:
    cur.execute(
        """
        SELECT user_id, consent_type, document_version, is_active,
               accepted_at, revoked_at
        FROM core_userconsent
        ORDER BY user_id, consent_type
        """
    )
    for row in cur.fetchall():
        print(row)

    print()
    cur.execute(
        """
        SELECT name FROM django_migrations
        WHERE app = 'core' AND name LIKE '004%' ORDER BY name
        """
    )
    print("004x applied:", [r[0] for r in cur.fetchall()])
