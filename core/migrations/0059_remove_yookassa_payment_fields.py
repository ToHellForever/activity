from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0058_robokassa_payment"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="order",
            name="yookassa_payment_id",
        ),
        migrations.RemoveField(
            model_name="order",
            name="yookassa_payment_data",
        ),
    ]
