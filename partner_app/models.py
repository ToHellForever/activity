from django.db import models
from django.core.validators import MinValueValidator
from core.models import CustomUser

class SalesReport(models.Model):
    """
    Модель для хранения сгенерированных отчётов о продажах.
    """
    REPORT_FORMAT_CHOICES = [
        ("pdf", "PDF"),
        ("csv", "CSV"),
        ("excel", "Excel"),
    ]

    partner = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        limit_choices_to={"user_type": "partner"},
        verbose_name="Партнёр",
    )
    period_start = models.DateField(verbose_name="Начало периода")
    period_end = models.DateField(verbose_name="Конец периода")
    report_type = models.CharField(
        max_length=10,
        choices=REPORT_FORMAT_CHOICES,
        verbose_name="Формат отчёта",
    )
    file_path = models.FileField(
        upload_to="reports/",
        verbose_name="Файл отчёта",
    )
    status = models.CharField(
        max_length=20,
        choices=[
            ("pending", "В обработке"),
            ("completed", "Готово"),
            ("failed", "Ошибка"),
        ],
        default="pending",
        verbose_name="Статус",
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Дата создания",
    )

    def __str__(self):
        return f"Отчёт для {self.partner.email} ({self.period_start} - {self.period_end})"

    class Meta:
        verbose_name = "Отчёт о продажах"
        verbose_name_plural = "Отчёты о продажах"
        ordering = ["-created_at"]