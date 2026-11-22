from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0060_robokassa_refunds"),
    ]

    operations = [
        migrations.AddField(
            model_name="robokassarefund",
            name="orders",
            field=models.ManyToManyField(
                blank=True,
                related_name="robokassa_refund_batches",
                to="core.order",
            ),
        ),
    ]
