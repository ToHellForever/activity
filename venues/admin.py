from django.contrib import admin
from .models import (
    VenueType,
    VenueEquipment,
    VenueAmenity,
    Venue,
    BookingRequest,
    VenueFormat,
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

    class Media:
        js = ("/static/js/map_admin.js", "/static/js/venue_admin.js")

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)

        # Делаем тариф первым полем в форме
        if "tariff" in form.base_fields:
            form.base_fields["tariff"].help_text = (
                "Выберите тарифный план. От него зависят доступные возможности: "
                "количество фото, наличие видео, приоритет в выдаче и другие параметры."
            )

        if "slug" in form.base_fields:
            form.base_fields["slug"].help_text = (
                "Оставьте это поле пустым, чтобы автоматически сгенерировать slug из названия."
            )
        return form


@admin.register(BookingRequest)
class BookingRequestAdmin(admin.ModelAdmin):
    list_display = ("id", "venue", "name", "event_date", "status", "created_at")
    list_filter = ("status", "created_at")
