from django.contrib.auth.models import AbstractUser
from django.db import models
import os
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator, FileExtensionValidator
from taggit.managers import TaggableManager
from django.utils import timezone
from core.mixins import VideoWatermarkMixin
from core.validators import validate_video_duration, compress_video


class CustomUser(AbstractUser, VideoWatermarkMixin):
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
        help_text="Максимальная длительность видео: 5 минут.",
        validators=[
            FileExtensionValidator(allowed_extensions=["mp4", "mov", "avi"]),
            validate_video_duration,
        ],
    )
    processed_video_business_card_hash = models.CharField(
        max_length=32,
        blank=True,
        null=True,
        verbose_name="Хэш обработанного видео визитки",
    )

    def save(self, *args, **kwargs):
        import os
        from django.conf import settings
        from core.utils import add_watermark_to_video

        # Сначала сохраняем модель, чтобы получить доступ к полям
        super().save(*args, **kwargs)

        # Проверяем, нужно ли обрабатывать видео визитку
        if self.video_business_card and self._should_process_video(
            self.video_business_card, self.processed_video_business_card_hash
        ):
            # Получаем путь к видео визитке
            video_path = self.video_business_card.path

            try:
                # Сжимаем видео
                from core.validators import compress_video

                compress_success = compress_video(video_path)
                if not compress_success:
                    print(f"Ошибка: не удалось сжать видео: {video_path}")
                    return

                # Добавляем водяной знак
                actual_watermark_path = os.path.join(
                    settings.BASE_DIR, "media", "watermark.png"
                )
                watermark_success = add_watermark_to_video(
                    video_path, actual_watermark_path, video_path
                )
                if not watermark_success:
                    print(
                        f"Ошибка: не удалось добавить водяной знак к видео: {video_path}"
                    )
                    return

            except Exception as e:
                print(f"Исключение при обработке видео: {str(e)}")
                raise

            # Обновляем хэш обработанной видео визитки
            self.processed_video_business_card_hash = self._get_video_hash(
                self.video_business_card
            )
            super().save(update_fields=["processed_video_business_card_hash"])


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


class Event(models.Model, VideoWatermarkMixin):
    """Модель для мероприятия."""

    STATUS_CHOICES = [
        ("on_moderation", "На модерации"),
        ("active", "Активно"),
        ("completed", "Завершено"),
        ("rejected", "Отклонено"),
    ]

    organizer = models.ForeignKey(
        User, on_delete=models.CASCADE, verbose_name="Организатор"
    )
    title = models.CharField(
        max_length=100, verbose_name="Название", help_text="Максимум 100 символов"
    )
    description_short = models.TextField(
        verbose_name="Краткое описание",
        help_text="Максимум 300 символов",
        max_length=500,
    )
    description_full = models.TextField(
        verbose_name="Полное описание",
        help_text="Максимум 3000 символов",
        max_length=5000,
    )
    date_time = models.DateTimeField(
        verbose_name="Дата и время",
        help_text="Мероприятие должно быть не ранее чем через 24 часа от текущего момента",
    )
    place_data = models.JSONField(
        verbose_name="Данные о местоположении",
        blank=True,
        null=True,
        help_text="Данные о местоположении в формате JSON (координаты, адрес, дополнительная информация)",
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="on_moderation",
        verbose_name="Статус",
    )
    refund_deadline_hours = models.PositiveIntegerField(
        default=24,  # По умолчанию 24 часа до начала мероприятия
        verbose_name="Срок возврата билетов (часы до начала)",
        help_text="Укажите, за сколько часов до начала мероприятия можно вернуть билет",
    )
    image = models.ImageField(
        upload_to="event_images/", verbose_name="Изображение", blank=True, null=True
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
        help_text="Максимальная длительность видео: 5 минут.",
        validators=[
            FileExtensionValidator(allowed_extensions=["mp4", "mov", "avi"]),
            validate_video_duration,
        ],
    )
    processed_video_url_hash = models.CharField(
        max_length=32,
        blank=True,
        null=True,
        verbose_name="Хэш обработанного видео мероприятия",
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
    has_sold_tickets = models.BooleanField(
        default=False,
        verbose_name="Проданы билеты",
        help_text="Флаг, указывающий, что на мероприятие проданы билеты",
    )

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        """
        Сохранение модели с добавлением водяного знака на изображения и видео.
        """
        import os
        from django.conf import settings
        from core.utils import add_watermark_to_image, add_watermark_to_video

        super().save(*args, **kwargs)

        # Путь к логотипу для водяного знака
        watermark_path = os.path.join(settings.BASE_DIR, "DejaVuSans-Bold.ttf")
        # Замените на путь к вашему логотипу
        actual_watermark_path = os.path.join(
            settings.BASE_DIR, "media", "watermark.png"
        )

        # Добавляем водяной знак на изображение
        if self.image:
            image_path = self.image.path
            add_watermark_to_image(image_path, actual_watermark_path, image_path)

        # Добавляем водяной знак на видео
        if self.video_url and self._should_process_video(
            self.video_url, self.processed_video_url_hash
        ):
            # Получаем путь к видео
            video_path = self.video_url.path

            # Проверяем существование файла перед обработкой
            if not os.path.exists(video_path):
                print(f"Файл видео не найден: {video_path}")
                return

            try:
                # Сжимаем видео
                from core.validators import compress_video

                compress_success = compress_video(video_path)
                if not compress_success:
                    print(f"Ошибка: не удалось сжать видео: {video_path}")
                    return

                # Добавляем водяной знак
                watermark_success = add_watermark_to_video(
                    video_path, actual_watermark_path, video_path
                )
                if not watermark_success:
                    print(
                        f"Ошибка: не удалось добавить водяной знак к видео: {video_path}"
                    )
                    return

            except Exception as e:
                print(f"Исключение при обработке видео: {str(e)}")
                raise

        self.processed_video_url_hash = self._get_video_hash(self.video_url)
        super().save(update_fields=["processed_video_url_hash"])

    def get_refund_deadline(self):
        """
        Возвращает крайний срок возврата билета.
        """
        return self.date_time - timezone.timedelta(hours=self.refund_deadline_hours)

    class Meta:
        verbose_name = "Мероприятие"
        verbose_name_plural = "Мероприятия"
        ordering = ["-date_time"]

    @property
    def get_place_address(self):
        """Возвращает адрес места проведения для админки"""
        if self.place_data and 'address' in self.place_data:
            return self.place_data['address']
        return "Не указано"


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

    def is_available(self, quantity=1):
        """Проверяет, доступно ли указанное количество билетов для покупки."""
        sold = sum(order.quantity for order in self.orders.all())
        return self.available_quantity >= sold + quantity

    def get_available_count(self):
        """Возвращает количество доступных билетов данного типа."""
        sold = sum(order.quantity for order in self.orders.all())
        return self.available_quantity - sold

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
    attended = models.BooleanField(default=False, verbose_name="Посетил мероприятие")
    is_paid = models.BooleanField(default=True, verbose_name="Оплачен")
    payment_deadline = models.DateTimeField(
        null=True, blank=True, verbose_name="Срок оплаты"
    )

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
    event = models.ForeignKey(
        Event,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Связанное мероприятие",
        help_text="Мероприятие, к которому относится обращение",
    )

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
