from django.db import models
from django.core.validators import MinValueValidator
from django.core.validators import FileExtensionValidator
from django.contrib.auth import get_user_model
from django.utils.text import slugify
from taggit.managers import TaggableManager
from django.urls import reverse
from core.validators import validate_video_duration
from core.mixins import VideoWatermarkMixin
import os
User = get_user_model()


class VenueFormat(models.Model):
    """Справочник форматов мероприятий."""

    name = models.CharField(
        max_length=100, unique=True, verbose_name="Формат мероприятия"
    )

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Формат мероприятия"
        verbose_name_plural = "Форматы мероприятий"


class VenueType(models.Model):
    """Справочник типов площадок."""

    name = models.CharField(max_length=100, unique=True, verbose_name="Тип площадки")

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Тип площадки"
        verbose_name_plural = "Типы площадок"


class VenueEquipment(models.Model):
    """Справочник оборудования."""

    name = models.CharField(max_length=100, unique=True, verbose_name="Оборудование")

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Оборудование"
        verbose_name_plural = "Оборудование"


class VenueAmenity(models.Model):
    """Справочник удобств."""

    name = models.CharField(max_length=100, unique=True, verbose_name="Удобство")

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Удобство"
        verbose_name_plural = "Удобства"


class Venue(VideoWatermarkMixin, models.Model):
    """Модель площадки для проведения мероприятий."""

    STATUS_CHOICES = [
        ("draft", "Черновик"),
        ("published", "Опубликовано"),
        ("archived", "Архив"),
    ]
    PLACEMENT_TARIFF_CHOICES = [
        ("basic", "Базовый"),
        ("extended", "Расширенный"),
        ("premium", "Премиум"),
    ]
    PRICE_UNIT_CHOICES = [
        ("hour", "В час"),
        ("day", "В день"),
        ("request", "По запросу"),
    ]

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
    city = models.CharField(max_length=100, default="Новосибирск", verbose_name="Город")
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

    parking = models.BooleanField(default=False, verbose_name="Парковка")

    equipment = models.ManyToManyField(
        VenueEquipment, blank=True, verbose_name="Оборудование"
    )
    amenities = models.ManyToManyField(
        VenueAmenity, blank=True, verbose_name="Удобства"
    )

    formats = TaggableManager(
        verbose_name="Подходит для формата",
        help_text="Выберите форматы: тренинг, мастер-класс и т.д.",
    )

    images = models.ImageField(
        upload_to="venue_images/", blank=True, verbose_name="Главное фото", null=True
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
    placement_tariff = models.CharField(
        max_length=20, choices=PLACEMENT_TARIFF_CHOICES, default="basic"
    )

    contacts_opened = models.BooleanField(
        default=False, verbose_name="Контакты открыты"
    )  # Для тарифов extended/premium

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # SEO поля
    meta_title = models.CharField(max_length=255, blank=True)
    meta_description = models.TextField(blank=True)

    def save(self, *args, **kwargs):
        if not self.slug:
            from slugify import slugify
            self.slug = slugify(self.title)

        # Обработка водяного знака для изображения
        if self.images:
            from django.conf import settings
            from core.utils import add_watermark_to_image

            # Путь к логотипу для водяного знака
            watermark_path = os.path.join(settings.MEDIA_ROOT, "watermark.png")

            if os.path.exists(watermark_path):
                image_path = self.images.path
                add_watermark_to_image(image_path, watermark_path, image_path)

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
