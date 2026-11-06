from django.contrib.postgres.indexes import GinIndex
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0053_faqcategory_icon_file"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="order",
            index=GinIndex(
                fields=["participant_data"],
                name="order_participant_data_gin",
            ),
        ),
    ]
