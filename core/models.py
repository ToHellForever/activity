from django.contrib.auth.models import AbstractUser
from django.db import models, transaction
import os
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator, FileExtensionValidator
from taggit.managers import TaggableManager
from django.utils import timezone
from core.mixins import VideoWatermarkMixin
from core.validators import validate_video_duration, compress_video

try:
    from core.redis_utils import get_lock

    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
from django.utils import timezone


class VideoWatermarkMixin:
    """Миксин для обработки видео с водяными знаками."""

    def _get_video_hash(self, video_field):
        if not video_field or not video_field.path:
            return None
        try:
            with open(video_field.path, "rb") as f:
                import hashlib

                return hashlib.md5(f.read()).hexdigest()
        except FileNotFoundError:
            return None

    def _should_process_video(self, video_field, hash_field):
        current_hash = self._get_video_hash(video_field)
        return current_hash != hash_field

    def delete_old_video(self, video_field_name, hash_field_name):
        """Удаляет старый файл видео и обнуляет хэш."""
        video_field = getattr(self, video_field_name)
        if video_field and os.path.exists(video_field.path):
            try:
                os.remove(video_field.path)
            except Exception as e:
                print(f"Ошибка удаления файла: {e}")
        setattr(self, hash_field_name, None)


class CustomUser(AbstractUser, VideoWatermarkMixin):
    USER_TYPE_CHOICES = (
        ("guest", "Гость"),
        ("visitor", "Посетитель"),
        ("partner", "Партнёр"),
    )
    user_type = models.CharField(
        max_length=10, choices=USER_TYPE_CHOICES, default="guest"
    )
    username = models.CharField(max_length=150, unique=True, verbose_name="Логин")
    is_verified = models.BooleanField(default=False)
    verification_status = models.CharField(
        max_length=20,
        choices=[
            ("not_submitted", "Не отправлено"),
            ("pending", "На рассмотрении"),
            ("approved", "Подтверждено"),
            ("rejected", "Отклонено"),
        ],
        default="not_submitted",
    )
    company_name = models.CharField(max_length=255, blank=True, null=True)
    phone_number = models.CharField(max_length=30, blank=True, null=True)
    logo = models.ImageField(upload_to="user_logos/", blank=True, null=True)
    social_links = models.TextField(blank=True, null=True)
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
        max_length=32, blank=True, null=True
    )
    VIDEO_PROCESSING_STATUS_CHOICES = (
        ("pending", "Ожидает обработки"),
        ("processing", "Обрабатывается"),
        ("completed", "Обработка завершена"),
        ("failed", "Ошибка обработки"),
    )
    video_business_card_processing_status = models.CharField(
        max_length=20,
        choices=VIDEO_PROCESSING_STATUS_CHOICES,
        default="pending",
        verbose_name="Статус обработки видео-визитки",
    )
    video_processing_status = models.CharField(
        max_length=20,
        choices=VIDEO_PROCESSING_STATUS_CHOICES,
        default="pending",
        verbose_name="Статус обработки видео",
    )

    def save(self, *args, **kwargs):
        # Проверяем замену видео-визитки
        if self.pk:
            old = CustomUser.objects.get(pk=self.pk)
            if old.video_business_card != self.video_business_card:
                self.delete_old_video(
                    "video_business_card", "processed_video_business_card_hash"
                )

        super().save(*args, **kwargs)


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


class Tag(models.Model):
    """Модель для тегов мероприятий."""

    name = models.CharField(
        max_length=50, unique=True, verbose_name="Название тега"
    )

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Тег"
        verbose_name_plural = "Теги"
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
    VIDEO_PROCESSING_STATUS_CHOICES = (
        ("pending", "Ожидает обработки"),
        ("processing", "Обрабатывается"),
        ("completed", "Обработка завершена"),
        ("failed", "Ошибка обработки"),
    )

    video_processing_status = models.CharField(
        max_length=20,
        choices=VIDEO_PROCESSING_STATUS_CHOICES,
        default="pending",
        verbose_name="Статус обработки видео",
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
    tags = models.ManyToManyField(
        Tag,
        blank=True,
        verbose_name="Теги",
        help_text="Выберите до 5 тегов для мероприятия"
    )
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
    duration = models.CharField(
        max_length=5,
        blank=True,
        null=True,
        verbose_name="Длительность (ЧЧ:ММ)",
        help_text="Формат: ЧЧ:ММ (например, 02:30 для 2 часов 30 минут)",
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
    rejection_reason = models.TextField(
        blank=True,
        null=True,
        verbose_name="Причина отклонения",
        help_text="Причина, по которой мероприятие было отклонено модератором",
    )

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        # Проверяем замену видео мероприятия
        if self.pk:
            old = Event.objects.get(pk=self.pk)
            if old.video_url != self.video_url:
                self.delete_old_video("video_url", "processed_video_url_hash")
                self.video_processing_status = "pending"

    def save(self, *args, **kwargs):
        """
        Сохранение модели с добавлением водяного знака на изображения
        и обновлением данных о местоположении.
        """
        import os
        import json
        from django.conf import settings
        from core.utils import add_watermark_to_image

        # Если есть данные о местоположении в отдельных полях, обновляем place_data
        if hasattr(self, '_place_data_updated'):
            # Преобразуем в словарь, если это строка
            place_data = {}
            if isinstance(self.place_data, str):
                try:
                    place_data = json.loads(self.place_data)
                except json.JSONDecodeError:
                    place_data = {}
            elif isinstance(self.place_data, dict):
                place_data = self.place_data.copy()

            # Обновляем адрес и координаты
            if hasattr(self, 'address') and self.address:
                place_data['address'] = self.address
            if hasattr(self, 'latitude') and self.latitude:
                place_data['latitude'] = float(self.latitude)
            if hasattr(self, 'longitude') and self.longitude:
                place_data['longitude'] = float(self.longitude)

            self.place_data = place_data

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
        if self.place_data and "address" in self.place_data:
            return self.place_data["address"]
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
        from django.db import transaction

        try:
            # Используем распределенную блокировку, если доступно
            if REDIS_AVAILABLE:
                with get_lock(self.pk, use_redis=True):
                    return self._check_availability(quantity)
            else:
                # Локальная блокировка через транзакции
                with transaction.atomic():
                    ticket = Ticket.objects.select_for_update().get(pk=self.pk)
                    return ticket._check_availability(quantity)
        except Ticket.DoesNotExist:
            return False

    def _check_availability(self, quantity):
        """Внутренний метод для проверки доступности с уже заблокированным билетом."""
        # Проверяем, не закрыты ли продажи для мероприятия
        if self.event.auto_close_sales_hours > 0:
            close_time = self.event.date_time - timezone.timedelta(
                hours=self.event.auto_close_sales_hours
            )
            if timezone.now() >= close_time:
                return False

        sold = sum(
            order.quantity for order in self.orders.exclude(payment_status="refunded")
        )
        return self.available_quantity >= sold + quantity

    def get_available_count(self):
        """Возвращает количество доступных билетов данного типа."""
        from django.db import transaction

        try:
            # Используем распределенную блокировку, если доступно
            if REDIS_AVAILABLE:
                with get_lock(self.pk, use_redis=True):
                    sold = sum(
                        order.quantity
                        for order in self.orders.exclude(payment_status="refunded")
                    )
                    return self.available_quantity - sold
            else:
                # Локальная блокировка через транзакции
                with transaction.atomic():
                    ticket = Ticket.objects.select_for_update().get(pk=self.pk)
                    sold = sum(
                        order.quantity
                        for order in ticket.orders.exclude(payment_status="refunded")
                    )
                    return ticket.available_quantity - sold
        except Ticket.DoesNotExist:
            return 0

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
    is_paid = models.BooleanField(default=False, verbose_name="Оплачен")
    payment_deadline = models.DateTimeField(
        null=True, blank=True, verbose_name="Срок оплаты"
    )
    platform_commission = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.00,
        verbose_name="Комиссия платформы",
        help_text="Сумма комиссии платформы, удержанная с этого заказа",
    )

    # Статус платежа
    PAYMENT_STATUS_CHOICES = [
        ("pending", "Ожидает оплаты"),
        ("succeeded", "Оплачено"),
        ("canceled", "Отменено"),
        ("refunded", "Возврат"),
    ]
    payment_status = models.CharField(
        max_length=20,
        choices=PAYMENT_STATUS_CHOICES,
        default="pending",
        verbose_name="Статус платежа",
    )

    # Тип покупки
    PURCHASE_TYPE_CHOICES = [
        ("paid_ticket", "Платный билет"),
        ("free_registration", "Бесплатная регистрация"),
        ("platform_request", "Заявка через платформу"),
    ]
    purchase_type = models.CharField(
        max_length=20,
        choices=PURCHASE_TYPE_CHOICES,
        default="paid_ticket",
        verbose_name="Тип покупки",
    )

    def save(self, *args, **kwargs):
        # Логирование изменения статуса платежа
        if self.pk:  # Если объект уже существует в базе
            original = Order.objects.get(pk=self.pk)
            if original.payment_status != self.payment_status:
                from django.contrib.auth import get_user_model

                User = get_user_model()
                admin_users = User.objects.filter(is_superuser=True)

                # Отправляем уведомление администраторам (можно заменить на logging, если нужно)
                for admin in admin_users:
                    print(
                        f"Уведомление для {admin.email}: Статус заказа #{self.id} изменён с {original.payment_status} на {self.payment_status}"
                    )

        super().save(*args, **kwargs)

    # Поля для хранения UTM-меток
    utm_source = models.CharField(
        max_length=100, blank=True, null=True, verbose_name="UTM Source"
    )
    utm_medium = models.CharField(
        max_length=100, blank=True, null=True, verbose_name="UTM Medium"
    )
    utm_campaign = models.CharField(
        max_length=100, blank=True, null=True, verbose_name="UTM Campaign"
    )
    utm_term = models.CharField(
        max_length=100, blank=True, null=True, verbose_name="UTM Term"
    )
    utm_content = models.CharField(
        max_length=100, blank=True, null=True, verbose_name="UTM Content"
    )

    def __str__(self):
        return f"Заказ #{self.id} - {self.ticket.name}"

    class Meta:
        verbose_name = "Заказ"
        verbose_name_plural = "Заказы"


class PayoutDetails(models.Model):
    """Модель для хранения реквизитов партнёра."""

    BANK_CHOICES = [
        ("sberbank", "Сбербанк"),
        ("tinkoff", "Тинькофф"),
        ("vtb", "ВТБ"),
        ("alfabank", "Альфа-Банк"),
        ("other", "Другой банк"),
    ]

    partner = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="Партнёр")
    bank_name = models.CharField(
        max_length=100, choices=BANK_CHOICES, verbose_name="Банк"
    )
    account_number = models.CharField(max_length=50, verbose_name="Номер счёта/карты")
    account_holder = models.CharField(max_length=255, verbose_name="Владелец счёта")
    inn = models.CharField(max_length=20, blank=True, null=True, verbose_name="ИНН")
    is_default = models.BooleanField(default=False, verbose_name="Основные реквизиты")

    def __str__(self):
        return (
            f"Реквизиты {self.partner.get_full_name()} - {self.get_bank_name_display()}"
        )

    class Meta:
        verbose_name = "Реквизиты для выплаты"
        verbose_name_plural = "Реквизиты для выплат"


class PayoutRequest(models.Model):
    """Модель для запроса выплаты партнером."""

    STATUS_CHOICES = [
        ("pending", "Ожидает"),
        ("processing", "В обработке"),
        ("paid", "Выплачено"),
        ("rejected", "Отклонено"),
        ("cancelled", "Отменено"),
    ]

    organizer = models.ForeignKey(
        User, on_delete=models.CASCADE, verbose_name="Партнёр"
    )
    amount = models.DecimalField(
        max_digits=10, decimal_places=2, verbose_name="Сумма к выплате"
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    payment_details = models.ForeignKey(
        PayoutDetails, on_delete=models.SET_NULL, null=True, verbose_name="Реквизиты"
    )
    comment = models.TextField(blank=True, null=True, verbose_name="Комментарий")

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
