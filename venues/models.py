from django.db import models
from django.core.validators import MinValueValidator
from django.core.validators import FileExtensionValidator
from django.contrib.auth import get_user_model
from django.utils.text import slugify
from taggit.managers import TaggableManager
from django.urls import reverse
from core.validators import validate_video_duration
from core.mixins import VideoWatermarkMixin
from unidecode import unidecode
import os

User = get_user_model()


class EquipmentCategory(models.Model):
    """Справочник категорий оборудования."""

    name = models.CharField(
        max_length=100, unique=True, verbose_name="Категория оборудования"
    )

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Категория оборудования"
        verbose_name_plural = "Категории оборудования"


# подкатегория для оборудования например: "Звук" - "Колонки", "Микрофон", "Свет" - "Прожекторы", "Декорации" - "Столы", "Стулья"
class EquipmentItem(models.Model):
    """Модель для конкретного оборудования, связанного с категорией."""

    category = models.ForeignKey(
        EquipmentCategory,
        on_delete=models.CASCADE,
        related_name="items",
        verbose_name="Категория",
    )
    name = models.CharField(max_length=100, verbose_name="Название оборудования")

    def __str__(self):
        return f"{self.category.name} - {self.name}"

    class Meta:
        verbose_name = "Элемент оборудования"
        verbose_name_plural = "Элементы оборудования"


class VenueType(models.Model):
    """Справочник типов площадок."""

    name = models.CharField(max_length=100, unique=True, verbose_name="Тип площадки")

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Тип площадки"
        verbose_name_plural = "Типы площадок"


class VenueFormat(models.Model):
    """Справочник форматов площадок."""

    name = models.CharField(max_length=100, unique=True, verbose_name="Формат площадки")

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Формат площадки"
        verbose_name_plural = "Форматы площадок"


class VenueImage(VideoWatermarkMixin, models.Model):
    """Модель для хранения фотографий площадки."""

    venue = models.ForeignKey(
        "Venue",
        on_delete=models.CASCADE,
        related_name="images",
        verbose_name="Площадка",
    )
    image = models.ImageField(upload_to="venue_images/", verbose_name="Фото")

    def __str__(self):
        return f"Фото для {self.venue.title}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

        # Обработка водяного знака для изображения
        if self.image:
            from django.conf import settings
            from core.utils import add_watermark_to_image

            # Путь к логотипу для водяного знака
            watermark_path = os.path.join(settings.MEDIA_ROOT, "watermark.png")

            if os.path.exists(watermark_path):
                image_path = self.image.path
                add_watermark_to_image(image_path, watermark_path, image_path)

    class Meta:
        verbose_name = "Фото площадки"
        verbose_name_plural = "Фото площадок"


class Venue(VideoWatermarkMixin, models.Model):
    """Модель площадки для проведения мероприятий."""

    STATUS_CHOICES = [
        ("draft", "Черновик"),
        ("published", "Опубликовано"),
        ("archived", "Архив"),
    ]
    TARIFF_CHOICES = [
        (1, "Free"),
        (2, "Standard"),
        (3, "Premium"),
    ]

    # Элементы оборудования, связанные с площадкой
    equipment_items = models.ManyToManyField(
        EquipmentItem,
        blank=True,
        verbose_name="Элементы оборудования",
        related_name="venues",
    )

    TARIFF_LIMITS = {
        1: {
            "max_photos": 1,
            "has_video": False,
            "priority": 1,
            "show_badge": False,
            "description_limit": 500,
            "show_in_collections": False,
            "contacts_level": "only_request",
            "badge_text": "",
        },
        2: {
            "max_photos": 10,
            "has_video": False,
            "priority": 2,
            "show_badge": True,
            "description_limit": 2000,
            "show_in_collections": True,
            "contacts_level": "request_or_show",
            "badge_text": "Партнёр",
        },
        3: {
            "max_photos": 25,
            "has_video": True,
            "priority": 3,
            "show_badge": True,
            "description_limit": 5000,
            "show_in_collections": True,
            "contacts_level": "direct",
            "badge_text": "Рекомендуем",
        },
    }
    PRICE_UNIT_CHOICES = [
        ("hour", "В час"),
        ("day", "В день"),
        ("request", "По запросу"),
    ]
    tariff = models.PositiveSmallIntegerField(
        choices=TARIFF_CHOICES,
        default=1,
        verbose_name="Тариф",
        help_text="Выберите тариф - от него зависят доступные возможности",
    )
    title = models.CharField(max_length=255, verbose_name="Название площадки")
    slug = models.SlugField(max_length=255, unique=True, blank=True)
    short_description = models.TextField(
        max_length=500, verbose_name="Краткое описание"
    )
    full_description = models.TextField(verbose_name="Полное описание")

    venue_type = models.ForeignKey(
        VenueType, on_delete=models.SET_NULL, null=True, verbose_name="Тип площадки"
    )

    address = models.CharField(max_length=255, verbose_name="Адрес")
    city = models.CharField(max_length=100, default="", verbose_name="Город")
    district = models.CharField(max_length=100, blank=True, verbose_name="Район")
    metro = models.CharField(max_length=100, blank=True, verbose_name="Ближайшее метро")

    latitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True
    )
    longitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True
    )

    area = models.FloatField(
        validators=[MinValueValidator(1)], verbose_name="Площадь (кв.м.)"
    )
    max_capacity = models.PositiveIntegerField(verbose_name="Вместимость (макс.)")

    price = models.DecimalField(
        max_digits=10, decimal_places=2, verbose_name="Стоимость аренды"
    )
    price_unit = models.CharField(
        max_length=20,
        choices=PRICE_UNIT_CHOICES,
        default="day",
        verbose_name="Единица стоимости",
    )
    equipment = models.ManyToManyField(
        EquipmentCategory, blank=True, verbose_name="Оборудование"
    )
    formats = models.ManyToManyField(
        VenueFormat,
        blank=True,
        verbose_name="Форматы площадки",
        help_text="Выберите форматы: тренинг, мастер-класс и т.д.",
    )
    video = models.FileField(
        upload_to="venue_videos/",
        blank=True,
        null=True,
        verbose_name="Видео (опционально)",
        validators=[
            FileExtensionValidator(allowed_extensions=["mp4", "mov", "avi"]),
            validate_video_duration,
        ],
    )
    processed_video_hash = models.CharField(
        max_length=64,
        blank=True,
        editable=False,
        verbose_name="Хэш обработанного видео",
    )

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")

    contacts_opened = models.BooleanField(
        default=False, verbose_name="Контакты открыты"
    )  # Для тарифов extended/premium

    contact_info = models.TextField(blank=True, verbose_name="Контактная информация")
    email = models.EmailField(
        blank=True,
        verbose_name="Email для уведомлений",
        help_text="Email, на который будут приходить уведомления о новых заявках",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # SEO поля
    meta_title = models.CharField(max_length=255, blank=True)
    meta_description = models.TextField(blank=True)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(unidecode(self.title))

        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("venue_detail", kwargs={"slug": self.slug})

    def __str__(self):
        return self.title

    class Meta:
        verbose_name = "Площадка"
        verbose_name_plural = "Площадки"


class BookingRequest(models.Model):
    """Модель заявки на площадку."""

    STATUS_CHOICES = [
        ("new", "Новая"),
        ("in_work", "В работе"),
        ("transferred", "Передана площадке"),
        ("closed", "Закрыта"),
    ]

    venue = models.ForeignKey(
        Venue, on_delete=models.CASCADE, related_name="booking_requests"
    )

    name = models.CharField(max_length=255)
    phone = models.CharField(max_length=30)
    email = models.EmailField(blank=True)

    event_date = models.DateTimeField()
    participants_count = models.PositiveIntegerField()
    event_format = models.CharField(max_length=100)

    comment = models.TextField(blank=True)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="new")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Заявка на {self.venue.title} от {self.name}"

    class Meta:
        verbose_name = "Заявка на площадку"
        verbose_name_plural = "Заявки на площадки"
