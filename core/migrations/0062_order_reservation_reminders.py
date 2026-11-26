from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0061_robokassa_refund_orders"),
    ]

    operations = [
        migrations.AddField(
            model_name="order",
            name="reminder_48_sent",
            field=models.BooleanField(
                default=False,
                verbose_name="Отправлено напоминание за 48 часов",
            ),
        ),
        migrations.AddField(
            model_name="order",
            name="reminder_24_sent",
            field=models.BooleanField(
                default=False,
                verbose_name="Отправлено напоминание за 24 часа",
            ),
        ),
    ]
