from django.contrib import admin
from django.utils.html import format_html
from django.core.exceptions import ValidationError
from .models import (
    VenueType,
    VenueEquipment,
    VenueAmenity,
    Venue,
    BookingRequest,
    VenueFormat,
    VenueImage,
)
from .forms import VenueForm


@admin.register(VenueType)
class VenueTypeAdmin(admin.ModelAdmin):
    list_display = ("name",)


@admin.register(VenueEquipment)
class VenueEquipmentAdmin(admin.ModelAdmin):
    list_display = ("name",)


@admin.register(VenueAmenity)
class VenueAmenityAdmin(admin.ModelAdmin):
    list_display = ("name",)


@admin.register(VenueFormat)
class VenueFormatAdmin(admin.ModelAdmin):
    list_display = ("name",)


class VenueImageInline(admin.TabularInline):
    model = VenueImage
    extra = 1
    fields = ('image', 'alt_text', 'image_preview')
    readonly_fields = ('image_preview',)

    def image_preview(self, obj):
        if obj.image:
            return format_html('<img src="{}" style="max-height: 100px; max-width: 100px;" />', obj.image.url)
        return ""
    image_preview.short_description = "Превью"

@admin.register(Venue)
class VenueAdmin(admin.ModelAdmin):
    form = VenueForm
    list_display = (
        "title",
        "city",
        "max_capacity",
        "price",
        "status",
        "tariff",
    )
    list_filter = ("status", "tariff", "city", "venue_type")
    search_fields = ("title", "address")
    filter_horizontal = (
        "equipment",
        "amenities",
    )
    inlines = [VenueImageInline]

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)

        # Делаем тариф первым полем в форме
        if "tariff" in form.base_fields:
            form.base_fields["tariff"].help_text = (
                "Выберите тарифный план:"
                "<ul style='margin: 5px 0 5px 20px;'>"
                "<li><strong>Free (1):</strong> 1 фото, без видео, краткое описание (500 символов), контакты только через заявку</li>"
                "<li><strong>Standard (2):</strong> до 10 фото, без видео, подробное описание (2000 символов), бейдж 'Партнёр', контакты по запросу</li>"
                "<li><strong>Premium (3):</strong> до 25 фото, с видео, расширенное описание (5000 символов), бейдж 'Рекомендуем', прямые контакты</li>"
                "</ul>"
            )

        if "slug" in form.base_fields:
            form.base_fields["slug"].help_text = (
                "Оставьте это поле пустым, чтобы автоматически сгенерировать slug из названия."
            )
        return form

    def save_formset(self, request, form, formset, change):
        super().save_formset(request, form, formset, change)
        if formset.model == VenueImage:
            venue = form.instance
            tariff = venue.tariff
            limits = venue.TARIFF_LIMITS.get(tariff, {})
            max_photos = limits.get("max_photos", 1)

            # Проверяем количество фотографий
            if VenueImage.objects.filter(venue=venue).count() > max_photos:
                raise ValidationError(
                    f"Для тарифа {venue.get_tariff_display()} можно загрузить не более {max_photos} фотографий."
                )

    class Media:
        js = ("/static/js/map_admin.js", "/static/js/venue_admin.js")


@admin.register(VenueImage)
class VenueImageAdmin(admin.ModelAdmin):
    list_display = ("venue", "alt_text")
    list_filter = ("venue",)

@admin.register(BookingRequest)
class BookingRequestAdmin(admin.ModelAdmin):
    list_display = ("id", "venue", "name", "event_date", "status", "created_at")
    list_filter = ("status", "created_at")
