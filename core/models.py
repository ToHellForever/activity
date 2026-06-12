from django.contrib.auth.models import AbstractUser
from django.db import models, transaction
import os
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator, FileExtensionValidator
from taggit.managers import TaggableManager
from django.utils import timezone
from core.mixins import VideoWatermarkMixin, ImageWatermarkMixin
try:
    from core.redis_utils import get_lock

    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
from django.utils import timezone


class CustomUser(AbstractUser, VideoWatermarkMixin):
    USER_TYPE_CHOICES = (
        ("guest", "Гость"),
        ("visitor", "Посетитель"),
        ("partner", "Партнёр"),
    )
    user_type = models.CharField(
        max_length=10, choices=USER_TYPE_CHOICES, default="guest", verbose_name='Тип пользователя'
    )
    username = models.CharField(max_length=150, unique=True, verbose_name="Логин")
    is_verified = models.BooleanField(default=False, verbose_name='Подтверждено')
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
    contact_person = models.CharField(max_length=255, blank=True, null=True, verbose_name="Контактное лицо (ФИО)")
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
        # Проверяем замену файлов
        if self.pk:
            old = CustomUser.objects.get(pk=self.pk)

            # Удаляем старое видео-визитку, если оно заменено
            if old.video_business_card != self.video_business_card:
                self.delete_old_video(
                    "video_business_card", "processed_video_business_card_hash"
                )

            # Удаляем старое лого, если оно заменено
            if old.logo != self.logo:
                self.delete_file_field("logo")

        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        """Удаляет все связанные файлы при удалении пользователя."""
        self.delete_file_field("logo")
        self.delete_file_field("video_business_card")
        super().delete(*args, **kwargs)

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

class EventPackage(models.Model):
    """Модель для пакетов мероприятий."""

    name = models.CharField(max_length=100, unique=True, verbose_name="Название пакета")
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, verbose_name="Цена пакета")
    max_active_events = models.PositiveIntegerField(default=1, verbose_name="Максимум активных мероприятий")
    event_card_type = models.CharField(max_length=20, choices=[
        ('basic', 'Базовая'),
        ('extended', 'Расширенная'),
        ('priority', 'Приоритетная'),
    ], default='basic', verbose_name="Тип карточки события")
    description_type = models.CharField(max_length=20, choices=[
        ('short', 'Краткое'),
        ('detailed', 'Подробное'),
    ], default='short', verbose_name="Тип описания")
    has_program_and_speakers = models.BooleanField(default=True, verbose_name="Программа и спикеры")
    max_photos = models.PositiveIntegerField(default=1, verbose_name="Максимум фото")
    has_video = models.BooleanField(default=False, verbose_name="Видео")
    has_platform_request = models.BooleanField(default=True, verbose_name="Заявка внутри платформы")
    has_free_registration = models.BooleanField(default=True, verbose_name="Зарегистрироваться (бесплатное мероприятие)")
    has_ticket_sales = models.BooleanField(default=True, verbose_name="Покупка билета")
    visibility_level = models.CharField(max_length=20, choices=[
        ('basic', 'Базовая'),
        ('enhanced', 'Повышенная'),
        ('priority', 'Приоритетная'),
    ], default='basic', verbose_name="Видимость в каталоге")
    has_collection_participation = models.BooleanField(default=False, verbose_name="Участие в подборках")
    is_monthly = models.BooleanField(default=False, verbose_name="Ежемесячная подписка")

    class Meta:
        verbose_name = "Пакет мероприятия"
        verbose_name_plural = "Пакеты мероприятий"

    def __str__(self):
        return self.name

    def can_create_event(self, user):
        """Проверяет, может ли пользователь создать новое мероприятие с этим пакетом"""
        active_events_count = Event.objects.filter(
            organizer=user,
            status__in=["active", "on_moderation"],
            package=self
        ).count()
        return active_events_count < self.max_active_events

class UserPackageSubscription(models.Model):
    """Модель для хранения информации о подписках пользователей на пакеты."""

    user = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        verbose_name="Пользователь"
    )
    package = models.ForeignKey(
        EventPackage,
        on_delete=models.CASCADE,
        verbose_name="Пакет",
        related_name="active_subscriptions"
    )
    start_date = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Дата начала подписки"
    )
    end_date = models.DateTimeField(
        verbose_name="Дата окончания подписки"
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name="Активна"
    )
    subscription_type = models.CharField(
        max_length=20,
        choices=[
            ('monthly', 'Ежемесячная подписка'),
            ('one_time', 'Разовый пакет'),
        ],
        default='monthly',
        verbose_name="Тип подписки"
    )
    scheduled_change_to = models.ForeignKey(
        EventPackage,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Запланированный пакет",
        help_text="Пакет, на который будет переключена подписка после окончания текущей",
        related_name="scheduled_subscriptions"
    )
    scheduled_change_date = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Дата запланированного изменения",
        help_text="Дата, когда должен вступить в силу запланированный пакет"
    )

    class Meta:
        verbose_name = "Подписка на пакет"
        verbose_name_plural = "Подписки на пакеты"

    def __str__(self):
        return f"{self.user.email} - {self.package.name}"

    def save(self, *args, **kwargs):
        """Обновляем статус активности подписки и дату окончания при сохранении."""
        # Only set end_date automatically for new subscriptions
        if not self.pk:  # If this is a new subscription
            if self.subscription_type == 'monthly':
                self.end_date = timezone.now() + timezone.timedelta(days=30)
            else:  # one_time
                self.end_date = timezone.now() + timezone.timedelta(days=365)

        if self.end_date < timezone.now():
            self.is_active = False
        super().save(*args, **kwargs)

    def can_change_package(self):
        """Проверяет, может ли пользователь изменить пакет."""
        return self.is_active

    def schedule_package_change(self, new_package):
        """Планирует изменение пакета после окончания текущего."""
        self.scheduled_change_to = new_package
        self.scheduled_change_date = self.end_date
        self.save()

    def apply_scheduled_change(self):
        """Применяет запланированное изменение пакета."""
        if self.scheduled_change_to and self.scheduled_change_date <= timezone.now():
            # Create new subscription with the scheduled package
            new_subscription = UserPackageSubscription.objects.create(
                user=self.user,
                package=self.scheduled_change_to,
                subscription_type='monthly' if self.scheduled_change_to.is_monthly else 'one_time',
                is_active=True
            )

            # Clear scheduled change
            self.scheduled_change_to = None
            self.scheduled_change_date = None
            self.is_active = False
            self.save()

            return new_subscription
        return None

class MainTag(models.Model):
    """Модель для основных тегов (категорий тегов)."""

    name = models.CharField(max_length=50, unique=True, verbose_name="Название основного тега")

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Основной тег"
        verbose_name_plural = "Основные теги"
        ordering = ["name"]

class Tag(models.Model):
    """Модель для подтегов мероприятий."""

    name = models.CharField(max_length=50, unique=True, verbose_name="Название подтега")
    main_tag = models.ForeignKey(
        MainTag,
        on_delete=models.CASCADE,
        related_name="subtags",
        verbose_name="Основной тег",
        help_text="Основной тег, к которому относится этот подтег",
        default=1  # Временно, для миграции
    )

    def __str__(self):
        return f"{self.main_tag.name} - {self.name}"

    class Meta:
        verbose_name = "Подтег"
        verbose_name_plural = "Подтеги"
        ordering = ["main_tag__name", "name"]

class Event(models.Model, VideoWatermarkMixin, ImageWatermarkMixin):
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
        upload_to="event_images/", 
        verbose_name="Изображение", 
        blank=True,
        null=True
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
        help_text="Выберите до 5 тегов для мероприятия",
    )
    video_url = models.FileField(
        upload_to="event_videos/",
        blank=True,
        null=True,
        verbose_name="Видео (загрузить)",
        help_text="Максимальная длительность видео: 5 минут.",
        validators=[
            FileExtensionValidator(allowed_extensions=["mp4", "mov", "avi"]),
        ]
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
    allow_platform_requests = models.BooleanField(
        default=False,
        verbose_name="Разрешить заявки через платформу",
        help_text="Если включено, пользователи смогут оставить заявку с вопросами",
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
    package = models.ForeignKey(
        EventPackage,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Пакет мероприятия",
        help_text="Выберите пакет для мероприятия",
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
        # Сохраняем старые значения для проверки замены файлов
        old_image = None
        old_video_url = None
        old_video_hash = None
        old_program_file = None
        
        if self.pk:
            old = Event.objects.get(pk=self.pk)
            old_image = old.image
            old_video_url = old.video_url
            old_video_hash = old.processed_video_url_hash
            old_program_file = old.program_file

        # Проверяем, было ли заменено видео ДО сохранения
        if self.pk and old_video_url != self.video_url and self.video_url:
            import logging
            logger = logging.getLogger(__name__)
            logger.info(f"Event {self.pk}: Video changed! old={old_video_url}, new={self.video_url}")
            # Обнуляем хэш ДО сохранения, чтобы сигнал post_save увидел None и запустил задачу
            self.processed_video_url_hash = None

        super().save(*args, **kwargs)

        # Удаляем старые файлы ПОСЛЕ сохранения (чтобы не удалить новые)
        if self.pk:
            # Удаляем старое видео, если оно заменено
            if old_video_url and (not self.video_url or old_video_url != self.video_url):
                self.delete_old_video_file(old_video_url, old_video_hash)

            # Удаляем старое изображение, если оно заменено
            if old_image != self.image and old_image:
                if not self.image or old_image != self.image:
                    self.delete_old_file(old_image)

            # Удаляем старую программу, если она заменена
            if old_program_file != self.program_file and old_program_file:
                if not self.program_file or old_program_file != self.program_file:
                    self.delete_old_file(old_program_file)

        # Если есть данные о местоположении в отдельных полях, обновляем place_data
        if hasattr(self, "_place_data_updated"):
            # Преобразуем в словарь, если это строка
            place_data = {}
            if isinstance(self.place_data, str):
                try:
                    import json
                    place_data = json.loads(self.place_data)
                except json.JSONDecodeError:
                    place_data = {}
            elif isinstance(self.place_data, dict):
                place_data = self.place_data.copy()

            # Обновляем адрес и координаты
            if hasattr(self, "address") and self.address:
                place_data["address"] = self.address
            if hasattr(self, "latitude") and self.latitude:
                place_data["latitude"] = float(self.latitude)
            if hasattr(self, "longitude") and self.longitude:
                place_data["longitude"] = float(self.longitude)

            self.place_data = place_data


    def get_refund_deadline(self):
        """
        Возвращает крайний срок возврата билета.
        """
        return self.date_time - timezone.timedelta(hours=self.refund_deadline_hours)

    def delete_old_file(self, old_file):
        """
        Удаляет старый файл по пути.
        Args:
            old_file: старый файл (FileField/ImageField) или путь к нему.
        """
        if not old_file:
            return

        try:
            # Получаем путь к файлу (может вызвать NotImplementedError для remote storage)
            file_path = old_file.path if hasattr(old_file, 'path') else str(old_file)
            
            # Проверяем, существует ли файл
            if os.path.exists(file_path):
                os.remove(file_path)
        except NotImplementedError:
            # Storage не поддерживает absolute paths (облачное хранилище)
            # Пытаемся удалить через storage
            try:
                from django.core.files.storage import default_storage
                file_name = str(old_file)
                if default_storage.exists(file_name):
                    default_storage.delete(file_name)
            except Exception as e:
                print(f"Ошибка удаления файла через storage: {e}")
        except Exception as e:
            print(f"Ошибка удаления файла: {e}")

    def delete_old_video_file(self, old_video, old_hash):
        """
        Удаляет старый видеофайл и обнуляет хэш.
        Args:
            old_video: старый видеофайл (FileField) или путь к нему.
            old_hash: хэш старого видео.
        """
        self.delete_old_file(old_video)
        # Обнуляем хэш, если это поле текущей модели
        if hasattr(self, 'processed_video_url_hash'):
            self.processed_video_url_hash = None
            # Сохраняем только хэш, не затрагивая другие поля
            Event.objects.filter(pk=self.pk).update(processed_video_url_hash=None)

    def delete(self, *args, **kwargs):
        """Удаляет все связанные файлы при удалении мероприятия."""
        self.delete_file_field("image")
        self.delete_file_field("video_url")
        self.delete_file_field("program_file")
        super().delete(*args, **kwargs)

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
                    available = ticket._check_availability(quantity)
                    print(
                        f"Checking availability for ticket {ticket.id}: available_quantity={ticket.available_quantity}, quantity={quantity}, available={available}"
                    )
                    return available
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
                print(f"Sales are closed for event {self.event.id}")
                return False

        sold = sum(
            order.quantity for order in self.orders.exclude(payment_status="refunded")
        )
        print(
            f"Ticket {self.id}: available_quantity={self.available_quantity}, sold={sold}, quantity={quantity}"
        )
        available = self.available_quantity >= sold + quantity
        print(f"Availability check result: {available}")
        return available

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

    ticket = models.ForeignKey(
        Ticket, on_delete=models.CASCADE, related_name="orders", verbose_name="Билет"
    )
    participant_data = models.JSONField(
        verbose_name="Данные участника"
    )  # Хранит имя, email и т.д.
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
    payment_id = models.CharField(
        max_length=255, null=True, blank=True, verbose_name="Идентификатор платежа"
    )
    yookassa_payment_id = models.CharField(
        max_length=255, null=True, blank=True, verbose_name="Идентификатор платежа в ЮКассе"
    )
    yookassa_payment_data = models.JSONField(
        null=True, blank=True, verbose_name="Данные платежа из ЮКассы"
    )
    platform_commission = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.00,
        verbose_name="Комиссия платформы",
        help_text="Сумма комиссии платформы, удержанная с этого заказа",
    )
    qr_codes = models.JSONField(
        default=list,
        blank=True,
        verbose_name="QR-коды",
        help_text="Список QR-кодов для каждого купленного билета",
    )
    # Статус платежа
    PAYMENT_STATUS_CHOICES = [
        ("pending", "Ожидает оплаты"),
        ("succeeded", "Оплачено"),
        ("canceled", "Отменено"),
        ("refunded", "Возврат"),
        ("reserved", "Забронировано"),
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

        # Генерация QR-кодов, если заказ новый или количество билетов изменилось
        if not self.pk or (self.pk and self.quantity != original.quantity):
            self._generate_qr_codes()

        # Удаляем флаг, чтобы избежать двойного вызова
        if hasattr(self, '_qr_codes_generated'):
            delattr(self, '_qr_codes_generated')

        super().save(*args, **kwargs)

    def _generate_qr_codes(self):
        """Генерация QR-кодов для каждого купленного билета."""
        import qrcode
        import uuid
        import os
        import logging
        from django.conf import settings

        logger = logging.getLogger(__name__)
        logger.info(f"Generating QR codes for order {self.id}")

        # Проверяем, что у заказа есть ID
        if not self.id:
            logger.error("Cannot generate QR codes: Order ID is None")
            return

        # Очищаем старые QR-коды, если они есть
        self.qr_codes = []

        # Генерация QR-кодов для каждого билета
        for i in range(self.quantity):
            # Уникальный идентификатор для каждого QR-кода
            qr_uuid = str(uuid.uuid4())

            # Формируем данные для QR-кода в читаемом формате, как в письме
            qr_text_data = f"Order ID: {self.id}, Ticket: {i + 1}"

            # Данные для QR-кода (можно расширить по необходимости)
            qr_data = {
                "order_id": self.id,
                "ticket_id": self.ticket.id,
                "participant_data": self.participant_data,
                "unique_id": qr_uuid,
                "text_data": qr_text_data,  # Читаемая строка для совместимости
            }

            # Создаем QR-код
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=4,
            )
            qr.add_data(qr_text_data)
            qr.make(fit=True)

            # Сохраняем QR-код в виде изображения
            img = qr.make_image(fill_color="black", back_color="white")

            # Путь для сохранения QR-кода
            qr_dir = os.path.join(settings.MEDIA_ROOT, "qr_codes")
            os.makedirs(qr_dir, exist_ok=True)
            qr_filename = f"qr_code_{qr_uuid}.png"
            qr_path = os.path.join(qr_dir, qr_filename)

            img.save(qr_path)
            logger.info(f"Saved QR code to {qr_path}")

            # Сохраняем путь к QR-коду в JSON-поле
            self.qr_codes.append(
                {
                    "unique_id": qr_uuid,
                    "qr_code_path": os.path.join("qr_codes", qr_filename),
                    "data": qr_data,
                }
            )

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

class EmailVerificationCode(models.Model):
    """
    Модель для хранения кодов подтверждения почты.
    """

    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="Пользователь")
    code = models.CharField(max_length=5, verbose_name="Код подтверждения")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    is_used = models.BooleanField(default=False, verbose_name="Использован")

    def __str__(self):
        return f"Код подтверждения для {self.user.email}"

    class Meta:
        verbose_name = "Код подтверждения почты"
        verbose_name_plural = "Коды подтверждения почты"

class EventImage(VideoWatermarkMixin, ImageWatermarkMixin, models.Model):
    """
    Модель для хранения фотографий мероприятий.
    """

    event = models.ForeignKey(
        "Event",
        on_delete=models.CASCADE,
        related_name="images",
        verbose_name="Мероприятие",
    )

    image = models.ImageField(
        upload_to="event_images/", 
        verbose_name="Фото мероприятия"
    )

    def __str__(self):
        return f"Фото для мероприятия: {self.event.title}"

    def save(self, *args, **kwargs):
            # Обработка водяного знака теперь выполняется на уровне хранилища
            # (YandexImageProcessingStorage или локальная обработка)
            # Не нужно добавлять водяной знак здесь
            super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        """Удаляет файл изображения при удалении записи."""
        self.delete_file_field("image")
        super().delete(*args, **kwargs)

    class Meta:
        verbose_name = "Фото мероприятия"
        verbose_name_plural = "Фото мероприятий"
