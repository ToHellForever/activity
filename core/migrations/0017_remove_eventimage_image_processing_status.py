# Удаление столбца image_processing_status из таблицы core_eventimage
# Это поле было добавлено напрямую в БД, но не нужно — удаляем его.

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0016_event_requires_strict_moderation'),
    ]

    operations = [
        migrations.RunSQL(
            # IF EXISTS: на чистой БД (тесты, новый деплой) колонки нет —
            # она добавлялась только вручную в рабочую базу.
            sql="ALTER TABLE core_eventimage DROP COLUMN IF EXISTS image_processing_status;",
            reverse_sql="ALTER TABLE core_eventimage ADD COLUMN IF NOT EXISTS image_processing_status VARCHAR(50) NOT NULL DEFAULT 'pending';",
        ),
    ]
