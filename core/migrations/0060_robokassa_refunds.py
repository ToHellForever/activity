from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0059_remove_yookassa_payment_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="robokassapayment",
            name="receipt_data",
            field=models.JSONField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="robokassapayment",
            name="operation_key",
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.CreateModel(
            name="RobokassaRefund",
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
                ("request_id", models.CharField(blank=True, max_length=64, null=True, unique=True)),
                ("amount", models.DecimalField(decimal_places=2, max_digits=10)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("requesting", "Отправляется"),
                            ("processing", "В обработке"),
                            ("succeeded", "Возвращён"),
                            ("canceled", "Отменён"),
                            ("failed", "Ошибка"),
                            ("unknown", "Статус неизвестен"),
                        ],
                        max_length=20,
                    ),
                ),
                ("response_data", models.JSONField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "order",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="robokassa_refunds",
                        to="core.order",
                    ),
                ),
                (
                    "order_ticket",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="robokassa_refunds",
                        to="core.orderticket",
                    ),
                ),
            ],
        ),
    ]
