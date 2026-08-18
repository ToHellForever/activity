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
                            print(f"Ошибка удаления из облака: {e}")
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
