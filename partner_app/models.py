from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
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
        storage=None,  # Будет установлено в apps.py
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
        return (
            f"Отчёт для {self.partner.email} ({self.period_start} - {self.period_end})"
        )

    class Meta:
        verbose_name = "Отчёт о продажах"
        verbose_name_plural = "Отчёты о продажах"
        ordering = ["-created_at"]


class ReportSchedule(models.Model):
    """
    Модель для хранения настроек расписания отправки отчётов.
    """

    FREQUENCY_CHOICES = [
        ("daily", "Ежедневно"),
        ("weekly", "Еженедельно"),
        ("monthly", "Ежемесячно"),
    ]

    PERIOD_CHOICES = [
        ("day", "За день"),
        ("week", "За неделю"),
        ("month", "За месяц"),
        ("custom", "Произвольный период"),
    ]

    partner = models.OneToOneField(
        CustomUser,
        on_delete=models.CASCADE,
        related_name="report_schedule",
        verbose_name="Партнёр",
    )
    is_active = models.BooleanField(default=True, verbose_name="Активна")
    frequency = models.CharField(
        max_length=10,
        choices=FREQUENCY_CHOICES,
        default="weekly",
        verbose_name="Частота",
    )
    report_format = models.CharField(
        max_length=10,
        choices=SalesReport.REPORT_FORMAT_CHOICES,
        default="pdf",
        verbose_name="Формат отчёта",
    )
    period_type = models.CharField(
        max_length=10,
        choices=PERIOD_CHOICES,
        default="week",
        verbose_name="Период отчёта",
    )
    email = models.EmailField(verbose_name="Email для отправки")
    day_of_week = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(6)],
        verbose_name="День недели (0-6)",
    )
    day_of_month = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MinValueValidator(31)],
        verbose_name="День месяца (1-31)",
    )
    custom_period_days = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1)],
        verbose_name="Количество дней для произвольного периода",
    )
    last_sent = models.DateTimeField(
        null=True, blank=True, verbose_name="Последняя отправка"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Создано")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Обновлено")

    def __str__(self):
        return f"Расписание отчётов для {self.partner.email}"

    class Meta:
        verbose_name = "Расписание отчётов"
        verbose_name_plural = "Расписания отчётов"
