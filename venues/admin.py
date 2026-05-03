from django.contrib import admin
from .models import (
    VenueType,
    VenueEquipment,
    VenueAmenity,
    Venue,
    BookingRequest,
    VenueFormat,
)


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
    list_display = (
        "title",
        "city",
        "max_capacity",
        "price",
        "status",
        "placement_tariff",
    )
    list_filter = ("status", "placement_tariff", "city", "venue_type")
    search_fields = ("title", "address")
    filter_horizontal = ("equipment", "amenities",)

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        if 'slug' in form.base_fields:
            form.base_fields['slug'].help_text = "Оставьте это поле пустым, чтобы автоматически сгенерировать slug из названия."
        return form


@admin.register(BookingRequest)
class BookingRequestAdmin(admin.ModelAdmin):
    list_display = ("id", "venue", "name", "event_date", "status", "created_at")
    list_filter = ("status", "created_at")
