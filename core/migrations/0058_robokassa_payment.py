from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0057_event_show_booking_button"),
    ]

    operations = [
        migrations.CreateModel(
            name="RobokassaPayment",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("amount", models.DecimalField(decimal_places=2, max_digits=10)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Ожидает оплаты"),
                            ("succeeded", "Оплачено"),
                            ("canceled", "Отменено"),
                        ],
                        default="pending",
                        max_length=20,
                    ),
                ),
                ("notification_data", models.JSONField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "orders",
                    models.ManyToManyField(
                        blank=True,
                        related_name="robokassa_payments",
                        to="core.order",
                    ),
                ),
            ],
        ),
    ]
