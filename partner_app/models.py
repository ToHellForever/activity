from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator, FileExtensionValidator
from django.conf import settings
from django.utils import timezone
from core.models import CustomUser
import os
import hashlib
import logging

logger = logging.getLogger(__name__)


class PartnerProfile(models.Model):
    """
    Модель для хранения данных регистрации партнёра.
    Все поля партнёра перенесены сюда из CustomUser.
    """

    REGISTRATION_TYPE_CHOICES = [
        ("physical", "Физическое лицо"),
        ("legal", "Юридическое лицо"),
        ("ip", "ИП"),
        ("self_employed", "Самозанятый"),
    ]

    VIDEO_PROCESSING_STATUS_CHOICES = (
        ("pending", "Ожидает обработки"),
        ("processing", "Обрабатывается"),
        ("completed", "Обработка завершена"),
        ("failed", "Ошибка обработки"),
    )

    user = models.OneToOneField(
        CustomUser,
        on_delete=models.CASCADE,
        related_name="partner_profile",
        verbose_name="Партнёр",
    )

    # === Тип регистрации ===
    registration_type = models.CharField(
        max_length=20,
        choices=REGISTRATION_TYPE_CHOICES,
        default="legal",
        verbose_name="Тип лица",
    )

    # === Основная информация ===
    company_name = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name="Название организации / ФИО",
    )
    short_name = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name="Краткое наименование, бренд/торговое имя",
    )
    description = models.TextField(
        blank=True,
        null=True,
        verbose_name="Описание организации (до 500 символов)",
        help_text="Кратко о деятельности",
        max_length=500,
    )

    # === Реквизиты ===
    ogrn = models.CharField(
        max_length=15,
        blank=True,
        null=True,
        verbose_name="ОГРН/ОГРНИП",
    )
    inn = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        verbose_name="ИНН",
    )
    kpp = models.CharField(
        max_length=9,
        blank=True,
        null=True,
        verbose_name="КПП",
    )

    # === Адреса ===
    postal_code = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        verbose_name="Почтовый индекс",
    )
    legal_address = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name="Юридический адрес",
    )
    actual_address = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name="Фактический адрес",
    )

    # === Контакты ===
    website = models.URLField(
        blank=True,
        null=True,
        verbose_name="Сайт компании URL",
    )
    contact_person = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name="Контактное лицо (ФИО)",
    )
    phone = models.CharField(
        max_length=30,
        blank=True,
        null=True,
        verbose_name="Телефон",
    )
    email = models.EmailField(
        blank=True,
        null=True,
        verbose_name="E-mail (для входа)",
    )
    additional_email = models.EmailField(
        blank=True,
        null=True,
        verbose_name="Дополнительный E-mail",
    )

    # === Социальные сети и ссылки ===
    social_links = models.TextField(
        blank=True,
        null=True,
        verbose_name="Социальные сети",
    )
    vk_link = models.URLField(
        blank=True,
        null=True,
        verbose_name="VK",
    )
    max_link = models.URLField(
        blank=True,
        null=True,
        verbose_name="MAX",
    )
    telegram_link = models.URLField(
        blank=True,
        null=True,
        verbose_name="Telegram",
    )

    # === Портфолио ===
    cases = models.TextField(
        blank=True,
        null=True,
        verbose_name="Кейсы/прошедшие мероприятия",
        help_text="Ссылки или краткое описание",
    )
    reviews = models.TextField(
        blank=True,
        null=True,
        verbose_name="Отзывы и публикации в СМИ",
        help_text="Ссылки",
    )

    # === Логотип ===
    logo = models.ImageField(
        upload_to="partner_logos/",
        blank=True,
        null=True,
        verbose_name="Логотип (PNG/SVG/JPG)",
        help_text="До 5 МБ",
    )

    # === Видео-визитка ===
    video_business_card = models.FileField(
        upload_to="partner_video/",
        blank=True,
        null=True,
        verbose_name="Видео-визитка",
        help_text="Максимальная длительность видео: 5 минут.",
        validators=[
            FileExtensionValidator(["mp4", "mov", "avi"]),
        ],
    )
    processed_video_business_card_hash = models.CharField(
        max_length=32,
        blank=True,
        null=True,
        verbose_name="Хэш обработанного видео",
    )
    video_business_card_processing_status = models.CharField(
        max_length=20,
        choices=VIDEO_PROCESSING_STATUS_CHOICES,
        default="pending",
        verbose_name="Статус обработки видео-визитки",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Дата создания",
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Дата обновления",
    )

    def __str__(self):
        return f"Профиль партнёра: {self.user.email}"

    def _get_video_hash(self, video_field):
        """
        Возвращает MD5-хэш видео.
        """
        if not video_field:
            return None
        try:
            video_path = video_field.path
            if not os.path.exists(video_path):
                return None
            with open(video_path, "rb") as f:
                return hashlib.md5(f.read()).hexdigest()
        except NotImplementedError:
            # Storage не поддерживает absolute paths (облачное хранилище)
            possible_paths = [
                os.path.join(settings.MEDIA_ROOT, video_field.name),
                os.path.join(settings.MEDIA_ROOT, 'partner_video', os.path.basename(video_field.name)),
                os.path.join(getattr(settings, 'MEDIA_TEMP_DIR', os.path.join(settings.BASE_DIR, 'media_temp')), video_field.name),
                os.path.join(getattr(settings, 'MEDIA_TEMP_DIR', os.path.join(settings.BASE_DIR, 'media_temp')), 'partner_video', os.path.basename(video_field.name)),
            ]
            for video_path in possible_paths:
                if os.path.exists(video_path):
                    try:
                        with open(video_path, "rb") as f:
                            return hashlib.md5(f.read()).hexdigest()
                    except Exception as e:
                        logger.error(f"Ошибка чтения файла {video_path}: {e}")
                        return None
            return None
        except Exception as e:
            logger.error(f"Ошибка получения хэша видео: {e}")
            return None

    def _should_process_video(self, video_field, hash_field):
        """
        Проверяет, нужно ли обрабатывать видео.
        """
        current_hash = self._get_video_hash(video_field)
        if current_hash is None:
            return False
        return current_hash != hash_field

    def delete_file_field(self, field_name):
        """Удаляет файл по имени поля."""
        field = self._meta.get_field(field_name)
        if field and self.pk:
            try:
                file_field = getattr(self, field_name)
                if file_field:
                    if getattr(settings, 'USE_YANDEX_CLOUD', False):
                        try:
                            from storages.backends.s3boto3 import S3Boto3Storage
                            s3_storage = S3Boto3Storage(
                                bucket_name=settings.AWS_STORAGE_BUCKET_NAME,
                                endpoint_url=settings.AWS_S3_ENDPOINT_URL,
                                access_key=settings.AWS_ACCESS_KEY_ID,
                                secret_key=settings.AWS_SECRET_ACCESS_KEY,
                                region_name=settings.AWS_S3_REGION_NAME,
                            )
                            if s3_storage.exists(str(file_field)):
                                s3_storage.delete(str(file_field))
                        except Exception as e:
                            logger.error("Ошибка удаления из облака: %s", e, exc_info=True)
                    else:
                        try:
                            if os.path.exists(file_field.path):
                                os.remove(file_field.path)
                        except NotImplementedError:
                            pass
            except Exception:
                pass
    def delete(self, *args, **kwargs):
        """Удаляет все связанные файлы при удалении пользователя."""
        # Удаляем файлы партнёра если есть профиль
        if hasattr(self, 'partner_profile'):
            try:
                profile = self.partner_profile
                profile.delete_file_field("logo")
                profile.delete_file_field("video_business_card")
                profile.delete()
            except Exception:
                pass
        super().delete(*args, **kwargs)
    class Meta:
        verbose_name = "Профиль партнёра"
        verbose_name_plural = "Профили партнёров"
        ordering = ["-created_at"]


class PortfolioImage(models.Model):
    """
    Изображение в портфолио партнёра.
    До 5 изображений на один элемент портфолио.
    """
    portfolio = models.ForeignKey(
        "PortfolioItem",
        on_delete=models.CASCADE,
        related_name="images",
        verbose_name="Портфолио",
    )
    image = models.ImageField(
        upload_to="portfolio_images/",
        verbose_name="Изображение",
        storage=None,  # storage = YandexImageProcessingStorage, устанавливается в apps.py
    )
    order = models.PositiveIntegerField(
        default=0,
        verbose_name="Порядок",
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Дата создания",
    )

    class Meta:
        verbose_name = "Изображение портфолио"
        verbose_name_plural = "Изображения портфолио"
        ordering = ["order"]

    def __str__(self):
        return f"Фото для '{self.portfolio.title}'"

    def save(self, *args, **kwargs):
        # Обработка (сжатие, водяной знак) выполняется на уровне хранилища
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        """Удаляет файл изображения при удалении записи."""
        if self.image:
            self.image.delete(save=False)
        super().delete(*args, **kwargs)


class PortfolioItem(models.Model):
    """
    Элемент портфолио партнёра (прошедшее мероприятие/кейс).
    """
    partner = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name="portfolio_items",
        limit_choices_to={"user_type": "partner"},
        verbose_name="Партнёр",
    )
    title = models.CharField(
        max_length=100,
        verbose_name="Название",
        help_text="До 100 символов",
    )
    event_date = models.DateField(
        verbose_name="Дата проведения",
    )
    city = models.CharField(
        max_length=100,
        verbose_name="Город",
    )
    description = models.TextField(
        max_length=1000,
        verbose_name="Описание",
        help_text="До 1000 символов",
    )
    links = models.JSONField(
        default=list,
        blank=True,
        verbose_name="Ссылки",
        help_text="До 3 ссылок (статьи, СМИ, соцсети)",
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Дата создания",
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Дата обновления",
    )

    class Meta:
        verbose_name = "Элемент портфолио"
        verbose_name_plural = "Элементы портфолио"
        ordering = ["-event_date"]

    def __str__(self):
        return f"{self.title} ({self.event_date})"

    @property
    def image_count(self):
        """Количество изображений в элементе портфолио."""
        return self.images.count()

    @property
    def valid_links(self):
        """Возвращает только валидные (не пустые) ссылки."""
        return [link for link in self.links if link and link.strip()]

    def delete(self, *args, **kwargs):
        """Перед удалением элемента портфолио удаляем файлы изображений по-отдельности.

        Это гарантирует удаление файлов из хранилища даже если удаление выполняется каскадом.
        """
        try:
            for img in list(self.images.all()):
                try:
                    img.delete()
                except Exception:
                    pass
        except Exception:
            pass

        return super().delete(*args, **kwargs)


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


from django.db.models.signals import pre_delete
from django.dispatch import receiver


@receiver(pre_delete, sender=PortfolioImage)
def delete_portfolioimage_file(sender, instance, **kwargs):
    """Signal receiver: удаляем файл изображения при удалении записи даже при bulk-delete."""
    try:
        if instance.image:
            instance.image.delete(save=False)
    except Exception:
        pass


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


class EventAccessLink(models.Model):
    """
    Временная ссылка/код доступа для контроля входа на мероприятие.
    Одно мероприятие может иметь несколько кодов (по одному на каждого контролёра).
    """
    event = models.ForeignKey(
        "core.Event",
        on_delete=models.CASCADE,
        related_name="access_links",
        verbose_name="Мероприятие",
    )
    name = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name="Имя контролёра",
        help_text="Например: 'Контролёр Алексей — вход №1'",
    )
    access_code = models.CharField(
        max_length=16,
        unique=True,
        verbose_name="Код доступа",
        help_text="Уникальный короткий код для страницы сканера",
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name="Активен",
        help_text="Если отключён — сканер не работает",
    )
    scanned_count = models.PositiveIntegerField(
        default=0,
        verbose_name="Отсканировано билетов",
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Создан")
    activated_at = models.DateTimeField(null=True, blank=True, verbose_name="Активирован")
    deactivated_at = models.DateTimeField(null=True, blank=True, verbose_name="Деактивирован")

    MAX_ACTIVE_LINKS = 2  # Максимум активных ссылок на одно мероприятие

    def __str__(self):
        status = "активен" if self.is_active else "неактивен"
        return f"{self.name or self.access_code} — {self.event.title} — {status}"

    def clean(self):
        """Проверяем ограничение на количество активных ссылок."""
        from django.core.exceptions import ValidationError
        
        if self.is_active and self.pk:
            # Считаем активные ссылки для этого мероприятия (исключая текущую)
            active_count = EventAccessLink.objects.filter(
                event=self.event,
                is_active=True,
            ).exclude(pk=self.pk).count()
            
            if active_count >= self.MAX_ACTIVE_LINKS:
                raise ValidationError(
                    f"Нельзя создать больше {self.MAX_ACTIVE_LINKS} активных ссылок "
                    f"на одно мероприятие. Сейчас уже активно {active_count}."
                )
        elif self.is_active and not self.pk:
            # Создаём новую ссылку
            active_count = EventAccessLink.objects.filter(
                event=self.event,
                is_active=True,
            ).count()
            
            if active_count >= self.MAX_ACTIVE_LINKS:
                raise ValidationError(
                    f"Нельзя создать больше {self.MAX_ACTIVE_LINKS} активных ссылок "
                    f"на одно мероприятие. Сейчас уже активно {active_count}."
                )

    def save(self, *args, **kwargs):
        self.clean()  # Вызываем валидацию перед сохранением
        if not self.access_code:
            self.access_code = self._generate_code()
        if self.is_active and not self.activated_at:
            self.activated_at = timezone.now()
        if not self.is_active and not self.deactivated_at:
            self.deactivated_at = timezone.now()
        super().save(*args, **kwargs)

    @property
    def scanner_url(self):
        from django.conf import settings
        site_url = getattr(settings, "SITE_URL", "")
        if not site_url:
            # Fallback — вернём относительный URL
            return f"/scanner/{self.access_code}/"
        # Убираем trailing slash
        site_url = site_url.rstrip("/")
        return f"{site_url}/scanner/{self.access_code}/"

    def _generate_code(self):
        import random
        import string
        while True:
            code = "".join(random.choices(string.ascii_uppercase + string.digits, k=8))
            if not EventAccessLink.objects.filter(access_code=code).exists():
                return code

    @classmethod
    def get_total_scanned(cls, event):
        """Общее количество отсканированных билетов по всем кодам мероприятия."""
        return cls.objects.filter(event=event, is_active=True).aggregate(
            total=models.Sum('scanned_count')
        )['total'] or 0

    class Meta:
        verbose_name = "Ссылка контроля входа"
        verbose_name_plural = "Ссылки контроля входа"
        ordering = ["-created_at"]


class EventChangeRequestImage(models.Model):
    """
    Дополнительное фото, предложенное партнёром в заявке на изменение.
    После одобрения заявки копируется в EventImage мероприятия.
    """
    change_request = models.ForeignKey(
        "EventChangeRequest",
        on_delete=models.CASCADE,
        related_name="new_gallery_images",
        verbose_name="Заявка на изменение",
    )
    image = models.ImageField(
        upload_to="change_requests/gallery/",
        verbose_name="Фото",
    )
    is_primary = models.BooleanField(
        default=False,
        verbose_name="Основное фото",
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Создано")

    class Meta:
        verbose_name = "Фото заявки на изменение"
        verbose_name_plural = "Фото заявок на изменение"
        ordering = ["id"]

    def __str__(self):
        return f"Фото заявки #{self.change_request_id}"

    def delete(self, *args, **kwargs):
        if self.image:
            self.image.delete(save=False)
        super().delete(*args, **kwargs)


class EventChangeRequest(models.Model):
    """
    Заявка на изменение мероприятия.

    Когда у мероприятия есть проданные билеты, прямое редактирование партнёру
    недоступно: он заполняет форму изменений, они сохраняются здесь как
    предложение (diff), а админ одобряет или отклоняет заявку. Изменения
    применяются к мероприятию только при одобрении.
    """

    STATUS_CHOICES = [
        ("pending", "На рассмотрении"),
        ("approved", "Одобрена"),
        ("rejected", "Отклонена"),
    ]

    event = models.ForeignKey(
        "core.Event",
        on_delete=models.CASCADE,
        related_name="change_requests",
        verbose_name="Мероприятие",
    )
    partner = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name="event_change_requests",
        verbose_name="Партнёр",
    )

    # === Предлагаемые изменения ===
    # Изменения обычных полей: {имя_поля: новое значение} (только отличающиеся)
    changes = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Изменения полей",
    )
    # Полный список билетов, предложенный партнёром
    tickets_data = models.JSONField(
        default=list,
        blank=True,
        verbose_name="Предложенные билеты",
    )
    tag_ids = models.JSONField(
        default=list,
        blank=True,
        verbose_name="ID тегов",
    )

    # === Файлы-заменители ===
    new_image = models.ImageField(
        upload_to="change_requests/images/",
        blank=True,
        null=True,
        verbose_name="Новое основное изображение",
    )
    new_video_url = models.FileField(
        upload_to="change_requests/videos/",
        blank=True,
        null=True,
        validators=[FileExtensionValidator(["mp4", "mov", "avi"])],
        verbose_name="Новое видео",
        # Используем YandexVideoProcessingStorage, чтобы видео сохранялось локально
        # и Celery-задача могла его обработать. Если использовать default storage
        # (YandexCloudWithProcessingStorage), файл загружается в облако и локальная
        # копия удаляется — Celery-задача не может найти файл для обработки.
    )
    new_program_file = models.FileField(
        upload_to="change_requests/programs/",
        blank=True,
        null=True,
        verbose_name="Новая программа (PDF)",
    )

    # === Флаги очистки медиа ===
    clear_image = models.BooleanField(default=False, verbose_name="Удалить основное фото")
    clear_video_url = models.BooleanField(default=False, verbose_name="Удалить видео")
    clear_program_file = models.BooleanField(default=False, verbose_name="Удалить программу")

    # === Галерея ===
    delete_image_ids = models.JSONField(
        default=list,
        blank=True,
        verbose_name="ID фото галереи к удалению",
    )
    primary_image_id = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="ID фото галереи, которое сделать основным",
    )
    primary_new_image_index = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="Индекс нового фото, которое сделать основным",
    )

    # === Модерация ===
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="pending",
        verbose_name="Статус",
    )
    admin_comment = models.TextField(
        blank=True,
        null=True,
        verbose_name="Комментарий администратора",
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_event_change_requests",
        verbose_name="Кто рассмотрел",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True, verbose_name="Дата рассмотрения")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Создана")

    class Meta:
        verbose_name = "Заявка на изменение мероприятия"
        verbose_name_plural = "Заявки на изменение мероприятий"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Заявка #{self.pk} на изменение «{self.event.title}» ({self.get_status_display()})"

    def clean(self):
        """Только одна активная заявка на мероприятие."""
        from django.core.exceptions import ValidationError

        if self.status == "pending" and self.event_id:
            qs = EventChangeRequest.objects.filter(event_id=self.event_id, status="pending")
            if self.pk:
                qs = qs.exclude(pk=self.pk)
            if qs.exists():
                raise ValidationError(
                    "По этому мероприятию уже есть заявка на рассмотрении."
                )

    @property
    def has_changes(self):
        """Есть ли в заявке хоть какие-то изменения."""
        return bool(
            self.changes
            or self.tickets_data
            or self.tag_ids
            or self.new_image
            or self.new_video_url
            or self.new_program_file
            or self.clear_image
            or self.clear_video_url
            or self.clear_program_file
            or self.delete_image_ids
            or self.primary_image_id
            or self.primary_new_image_index is not None
            or self.new_gallery_images.exists()
        )

    def get_field_diff_rows(self):
        """
        Возвращает список кортежей (название поля, текущее значение, предложенное)
        для отображения diff в админке.
        """
        from core.models import Event, Category, Format, EventPackage

        labels = {
            f.name: f.verbose_name for f in Event._meta.fields
        }
        rows = []
        for field_name, new_value in (self.changes or {}).items():
            current_value = getattr(self.event, field_name, None)
            if field_name in ("category", "format", "package"):
                model = {"category": Category, "format": Format, "package": EventPackage}[field_name]
                current = model.objects.filter(pk=current_value).first() if current_value else None
                proposed = model.objects.filter(pk=new_value).first() if new_value else None
                current_value = str(current) if current else "—"
                new_value = str(proposed) if proposed else "—"
            elif field_name == "date_time":
                fmt = "%d.%m.%Y %H:%M"
                current_value = timezone.localtime(current_value).strftime(fmt) if current_value else "—"
                new_value = timezone.localtime(new_value).strftime(fmt) if new_value else "—"
            rows.append((labels.get(field_name, field_name), current_value, new_value))
        return rows

    def apply_to_event(self, admin_user):
        """
        Применяет предложенные изменения к мероприятию.
        Вызывать только при одобрении заявки (внутри transaction.atomic()).
        """
        from django.db import transaction
        from django.core.files.base import File
        from django.utils.dateparse import parse_datetime as django_parse_datetime
        from core.models import EventImage, Ticket

        event = self.event

        with transaction.atomic():
            # 1. Обычные поля
            for field_name, value in (self.changes or {}).items():
                # Дата приходит из JSON в виде ISO-строки — парсим обратно
                if field_name == "date_time" and isinstance(value, str):
                    parsed = django_parse_datetime(value)
                    value = timezone.make_aware(parsed) if parsed and timezone.is_naive(parsed) else (parsed or value)
                setattr(event, field_name, value)

            # 2. Основные медиафайлы
            if self.clear_image and event.image:
                event.image = None
            if self.clear_video_url and event.video_url:
                event.video_url = None
            if self.clear_program_file and event.program_file:
                event.program_file = None

            if self.new_image:
                with self.new_image.open("rb") as f:
                    event.image.save(os.path.basename(self.new_image.name), File(f), save=False)
            video_was_updated = False
            if self.new_video_url:
                with self.new_video_url.open("rb") as f:
                    event.video_url.save(os.path.basename(self.new_video_url.name), File(f), save=False)
                # save=False не сохраняет в БД — обновляем вручную
                event.video_url.name = os.path.basename(self.new_video_url.name)
                # Сбрасываем статус обработки видео
                event.video_processing_status = "pending"
                event.processed_video_url_hash = None
                video_was_updated = True
            if self.new_program_file:
                with self.new_program_file.open("rb") as f:
                    event.program_file.save(os.path.basename(self.new_program_file.name), File(f), save=False)

            # Сохраняем event — video_url сохранится через update_fields
            if video_was_updated:
                event.save(update_fields=[
                    "video_url", "video_processing_status", "processed_video_url_hash"
                ])
            else:
                event.save()

            # Если было новое видео — запускаем обработку синхронно
            if video_was_updated:
                logger.info("APPLY_TO_EVENT: Processing video for Event %s", event.id)
                from core.tasks import process_video_task
                process_video_task(
                    model_name='Event',
                    instance_id=event.id,
                    video_field_name='video_url',
                    hash_field_name='processed_video_url_hash',
                    status_field_name='video_processing_status'
                )
                # Удаляем старую копию new_video_url после успешного копирования
                self.new_video_url.delete(save=False)

            # 3. Теги
            if self.tag_ids:
                event.tags.set(self.tag_ids[:5])

            # 4. Галерея: удаление отмеченных фото
            delete_ids = [i for i in (self.delete_image_ids or [])]
            if delete_ids:
                for img in EventImage.objects.filter(event=event, id__in=delete_ids):
                    img.delete()

            # 5. Галерея: добавление новых фото
            created_images = []
            for req_image in self.new_gallery_images.all():
                with req_image.image.open("rb") as f:
                    new_img = EventImage(event=event)
                    new_img.image.save(os.path.basename(req_image.image.name), File(f), save=False)
                    new_img.is_primary = req_image.is_primary
                    new_img.save()
                    created_images.append(new_img)

            # 6. Основное фото галереи
            if self.primary_image_id:
                EventImage.objects.filter(event=event).update(is_primary=False)
                img = EventImage.objects.filter(event=event, id=self.primary_image_id).first()
                if img:
                    img.is_primary = True
                    img.save(update_fields=["is_primary"])
            elif self.primary_new_image_index is not None and created_images:
                idx = self.primary_new_image_index
                if 0 <= idx < len(created_images):
                    EventImage.objects.filter(event=event).update(is_primary=False)
                    created_images[idx].is_primary = True
                    created_images[idx].save(update_fields=["is_primary"])
            elif created_images:
                # Новые фото есть, основное не выбрано — первое новое становится основным
                EventImage.objects.filter(event=event).update(is_primary=False)
                created_images[0].is_primary = True
                created_images[0].save(update_fields=["is_primary"])

            # Синхронизируем Event.image с основным EventImage
            event.set_primary_from_event_images()

            # 7. Билеты: обновляем существующие по названию, создаём новые.
            # Билеты с проданными заказами не удаляем и не пересоздаём —
            # обновляем их поля на месте, чтобы не потерять историю заказов.
            for row in self.tickets_data or []:
                try:
                    price = float(str(row.get("price", "0")).replace(",", "."))
                    quantity = int(row.get("quantity", 0))
                except (TypeError, ValueError):
                    continue
                if not row.get("name") or quantity <= 0:
                    continue
                ticket = event.tickets.filter(name__iexact=row["name"]).first()
                ticket_kwargs = {
                    "price": price,
                    "available_quantity": quantity,
                    "ticket_description": row.get("description") or "",
                    "is_per_person": bool(row.get("is_per_person")),
                    "min_quantity": int(row.get("min_quantity") or 1),
                }
                if ticket:
                    for field, val in ticket_kwargs.items():
                        setattr(ticket, field, val)
                    ticket.save()
                else:
                    event.tickets.create(name=row["name"], color=Ticket().get_random_color(), **ticket_kwargs)

            # 8. Помечаем заявку одобренной
            self.status = "approved"
            self.reviewed_by = admin_user
            self.reviewed_at = timezone.now()
            self.save(update_fields=["status", "reviewed_by", "reviewed_at"])

    def reject(self, admin_user, comment=""):
        """Отклоняет заявку."""
        self.status = "rejected"
        self.admin_comment = comment or ""
        self.reviewed_by = admin_user
        self.reviewed_at = timezone.now()
        self.save(update_fields=["status", "admin_comment", "reviewed_by", "reviewed_at"])

    def notify_partner(self):
        """Отправляет партнёру письмо о результате рассмотрения заявки."""
        from django.core.mail import send_mail
        from django.conf import settings as dj_settings

        if self.status == "approved":
            subject = f"Заявка на изменение мероприятия «{self.event.title}» одобрена"
            message = (
                f"Здравствуйте, {self.partner.first_name or self.partner.email}!\n\n"
                f"Ваша заявка на изменение мероприятия «{self.event.title}» одобрена. "
                f"Изменения применены к мероприятию.\n\n"
                f"С уважением,\nАдминистрация платформы"
            )
        else:
            subject = f"Заявка на изменение мероприятия «{self.event.title}» отклонена"
            message = (
                f"Здравствуйте, {self.partner.first_name or self.partner.email}!\n\n"
                f"К сожалению, ваша заявка на изменение мероприятия «{self.event.title}» отклонена.\n"
                + (f"Комментарий администратора: {self.admin_comment}\n" if self.admin_comment else "")
                + "\nС уважением,\nАдминистрация платформы"
            )
        try:
            send_mail(subject, message, dj_settings.DEFAULT_FROM_EMAIL, [self.partner.email])
        except Exception as e:
            logger.error("Не удалось отправить письмо о заявке #%s: %s", self.pk, e)
