from django.db import migrations, models


def create_venue_equipment_table(apps, schema_editor):
    # Создаем промежуточную таблицу для связи площадок и категорий оборудования
    schema_editor.execute("""
        CREATE TABLE venues_venue_equipment (
            id SERIAL PRIMARY KEY,
            venue_id INTEGER NOT NULL,
            equipmentcategory_id INTEGER NOT NULL,
            FOREIGN KEY (venue_id) REFERENCES venues_venue(id) ON DELETE CASCADE,
            FOREIGN KEY (equipmentcategory_id) REFERENCES venues_equipmentcategory(id) ON DELETE CASCADE,
            UNIQUE (venue_id, equipmentcategory_id)
        )
        """)


def reverse_create_venue_equipment_table(apps, schema_editor):
    # Удаляем таблицу при откате миграции
    schema_editor.execute("""
        DROP TABLE venues_venue_equipment
        """)


class Migration(migrations.Migration):
    dependencies = [
        ("venues", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(
            create_venue_equipment_table, reverse_create_venue_equipment_table
        ),
    ]
