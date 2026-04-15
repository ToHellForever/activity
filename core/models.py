from django.contrib.auth.models import AbstractUser
from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator, FileExtensionValidator
from core.validators import validate_and_compress_video
from taggit.managers import TaggableManager


class CustomUser(AbstractUser):
    """Модель для пользователя."""

    USER_TYPE_CHOICES = (
        ("guest", "Гость"),
        ("visitor", "Посетитель"),
        ("partner", "Партнёр"),
    )
    user_type = models.CharField(
        max_length=10, choices=USER_TYPE_CHOICES, default="guest"
    )
    username = models.CharField(max_length=150, unique=True, verbose_name="Логин")
    is_verified = models.BooleanField(default=False, verbose_name="Подтверждён")
    verification_status = models.CharField(
        max_length=20,
        choices=[
            ("not_submitted", "Не отправлено"),
            ("pending", "На рассмотрении"),
            ("approved", "Подтверждено"),
            ("rejected", "Отклонено"),
        ],
        default="not_submitted",
        verbose_name="Статус верификации",
    )
    company_name = models.CharField(
        max_length=255, blank=True, null=True, verbose_name="Название компании"
    )
    phone_number = models.CharField(
        max_length=30, blank=True, null=True, verbose_name="Телефон"
    )
    logo = models.ImageField(
        upload_to="user_logos/", blank=True, null=True, verbose_name="Фото / Логотип"
    )
    social_links = models.TextField(blank=True, null=True, verbose_name="Соцсети")
    video_business_card = models.FileField(
        upload_to="partner_video/",
        blank=True,
        null=True,
        verbose_name="Видео (загрузить)",
        validators=[
            FileExtensionValidator(allowed_extensions=["mp4", "mov", "avi"]),
            validate_and_compress_video,
        ],
    )

    def save(self, *args, **kwargs):
        """
        Сохранение модели пользователя с обработкой сжатого видео.
        """
        # Если есть сжатое видео, сохраняем его перед сохранением модели
        if hasattr(self, "_compressed_path") and self._compressed_path:
            from core.utils import compress_and_replace_video_field

            compress_and_replace_video_field(self, self._compressed_path)
            # Удаляем временный файл после сохранения
            try:
                import os

                os.unlink(self._compressed_path)
            except:
                pass
            delattr(self, "_compressed_path")

        super().save(*args, **kwargs)

    class Meta:
        verbose_name = "Пользователь"
        verbose_name_plural = "Пользователи"


User = get_user_model()


class PartnerDocument(models.Model):
    """
    Модель для хранения документов партнёра, загруженных для верификации.
    """

    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="Партнёр")
    document = models.FileField(upload_to="partner_documents/", verbose_name="Документ")
    uploaded_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата загрузки")
    is_approved = models.BooleanField(
        default=False, verbose_name="Подтверждено модератором"
    )
    reviewed_at = models.DateTimeField(
        blank=True, null=True, verbose_name="Дата проверки"
    )
    reviewer = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_documents",
        verbose_name="Модератор",
    )

    def __str__(self):
        return f"Документ {self.user.get_full_name()} - {'подтверждён' if self.is_approved else 'на проверке'}"

    class Meta:
        verbose_name = "Документ партнёра"
        verbose_name_plural = "Документы партнёров"


class Category(models.Model):
    """Модель для категорий мероприятий."""

    name = models.CharField(
        max_length=100, unique=True, verbose_name="Название категории"
    )

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Категория"
        verbose_name_plural = "Категории"
        ordering = ["name"]


class Event(models.Model):
    """Модель для мероприятия."""

    STATUS_CHOICES = [
        ("on_moderation", "На модерации"),
        ("active", "Активно"),
        ("completed", "Завершено"),
        ("archived", "Архив"),
    ]

    organizer = models.ForeignKey(
        User, on_delete=models.CASCADE, verbose_name="Организатор"
    )
    title = models.CharField(max_length=255, verbose_name="Название")
    description_short = models.TextField(verbose_name="Краткое описание")
    description_full = models.TextField(verbose_name="Полное описание")
    date_time = models.DateTimeField(verbose_name="Дата и время")
    place = models.CharField(max_length=255, verbose_name="Место проведения")
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="on_moderation",
        verbose_name="Статус",
    )
    image = models.ImageField(
        upload_to="event_images/", blank=True, null=True, verbose_name="Изображение"
    )

    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Категория",
    )
    tags = TaggableManager(verbose_name="Теги", blank=True)
    video_url = models.FileField(
        upload_to="event_videos/",
        blank=True,
        null=True,
        verbose_name="Видео (загрузить)",
        validators=[
            FileExtensionValidator(allowed_extensions=["mp4", "mov", "avi"]),
            validate_and_compress_video,
        ],
    )
    program_file = models.FileField(
        upload_to="event_programs/",
        blank=True,
        null=True,
        verbose_name="Программа (PDF)",
    )
    allow_booking_without_payment = models.BooleanField(
        default=False, verbose_name="Разрешить бронирование без оплаты"
    )
    # Автоматическое закрытие продаж (в часах)
    auto_close_sales_hours = models.PositiveIntegerField(
        default=0,
        verbose_name="Закрыть продажи за (часов)",
        help_text="0 - не закрывать автоматически",
    )
    commission_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=10.00,  # Ставим дефолтное значение
        verbose_name="Комиссия (%)",
    )

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        """
        Сохранение модели с обработкой сжатого видео.
        """
        # Если есть сжатое видео, сохраняем его перед сохранением модели
        if hasattr(self, "_compressed_path") and self._compressed_path:
            from core.utils import compress_and_replace_video_field

            compress_and_replace_video_field(
                self, self._compressed_path, "video_business_card"
            )
            # Удаляем временный файл после сохранения
            try:
                import os

                os.unlink(self._compressed_path)
            except:
                pass
            delattr(self, "_compressed_path")

        super().save(*args, **kwargs)

    class Meta:
        verbose_name = "Мероприятие"
        verbose_name_plural = "Мероприятия"
        ordering = ["-date_time"]


class Ticket(models.Model):
    """Модель для типа билета (VIP, Стандарт)."""

    event = models.ForeignKey(
        Event,
        on_delete=models.CASCADE,
        related_name="tickets",
        verbose_name="Мероприятие",
    )
    name = models.CharField(max_length=50, verbose_name="Название билета")
    price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Цена")
    available_quantity = models.PositiveIntegerField(verbose_name="Количество мест")

    def __str__(self):
        return f"{self.name} ({self.event.title})"

    def is_available(self):
        """Проверяет, доступен ли билет для покупки."""
        return self.available_quantity > self.orders.count()

    def get_sold_count(self):
        """Возвращает количество проданных билетов данного типа."""
        return self.orders.count()

    class Meta:
        verbose_name = "Билет"
        verbose_name_plural = "Билеты"


class Order(models.Model):
    """Модель для заказа (покупки)."""

    participant_data = models.JSONField(
        verbose_name="Данные участника"
    )  # Хранит имя, email и т.д.
    ticket = models.ForeignKey(
        Ticket, on_delete=models.CASCADE, related_name="orders", verbose_name="Билет"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    total_price = models.DecimalField(
        max_digits=10, decimal_places=2, verbose_name="Общая стоимость"
    )
    quantity = models.PositiveIntegerField(default=1, verbose_name="Количество билетов")

    def __str__(self):
        return f"Заказ #{self.id} - {self.ticket.name}"

    class Meta:
        verbose_name = "Заказ"
        verbose_name_plural = "Заказы"


class PayoutRequest(models.Model):
    """Модель для запроса выплаты партнером."""

    STATUS_CHOICES = [
        ("pending", "Ожидает"),
        ("processing", "В обработке"),
        ("paid", "Выплачено"),
        ("rejected", "Отклонено"),
    ]

    organizer = models.ForeignKey(User, on_delete=models.CASCADE)
    amount = models.DecimalField(
        max_digits=10, decimal_places=2, verbose_name="Сумма к выплате"
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    created_at = models.DateTimeField(auto_now_add=True)
    payout_method = models.JSONField(
        verbose_name="Реквизиты для выплаты"
    )  # Хранит номер счета, ИНН и т.д.

    def __str__(self):
        return f"Запрос #{self.id} - {self.get_status_display()}"

    class Meta:
        verbose_name = "Запрос на выплату"
        verbose_name_plural = "Запросы на выплату"


class SupportTicket(models.Model):
    STATUS_CHOICES = [
        ("new", "Новое"),
        ("in_progress", "В работе"),
        ("closed", "Закрыто"),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    subject = models.CharField(max_length=255, verbose_name="Тема")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="new")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Тикет #{self.id} - {self.subject}"

    # Это свойство поможет нам легко получить все сообщения чата
    @property
    def messages(self):
        return self.supportmessage_set.all().order_by("created_at")


class SupportAttachment(models.Model):
    """
    Модель для вложений в сообщениях поддержки.
    """

    message = models.ForeignKey(
        "SupportMessage", on_delete=models.CASCADE, related_name="attachments"
    )
    file = models.FileField(upload_to="support_attachments/", verbose_name="Файл")
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Вложение для сообщения #{self.message.id}"


class SupportMessage(models.Model):
    """
    Модель для одного сообщения в чате поддержки.
    """

    ticket = models.ForeignKey(
        SupportTicket, on_delete=models.CASCADE, related_name="messages"
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE)  # Кто отправил сообщение
    is_from_user = models.BooleanField(
        default=True
    )  # True - Пользователь, False - Модератор
    text = models.TextField(verbose_name="Текст сообщения")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Сообщение к тикету #{self.ticket.id}"
