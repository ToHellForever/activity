from django.db import migrations, models


def create_equipmentitem_table(apps, schema_editor):
    schema_editor.execute("""
        CREATE TABLE venues_equipmentitem (
            id SERIAL PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            category_id INTEGER NOT NULL,
            FOREIGN KEY (category_id) REFERENCES venues_equipmentcategory(id) ON DELETE CASCADE
        )
        """)


def reverse_create_equipmentitem_table(apps, schema_editor):
    schema_editor.execute("DROP TABLE venues_equipmentitem")


class Migration(migrations.Migration):
    dependencies = [
        ("venues", "0002_create_venue_equipment_table"),
    ]

    operations = [
        migrations.RunPython(
            create_equipmentitem_table, reverse_create_equipmentitem_table
        ),
    ]
