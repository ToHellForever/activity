from django.contrib import admin
from .models import VenueType, VenueEquipment, VenueAmenity, Venue, BookingRequest

@admin.register(VenueType)
class VenueTypeAdmin(admin.ModelAdmin):
    list_display = ('name',)
    
@admin.register(VenueEquipment)
class VenueEquipmentAdmin(admin.ModelAdmin):
    list_display = ('name',)

@admin.register(VenueAmenity)
class VenueAmenityAdmin(admin.ModelAdmin):
    list_display = ('name',)

@admin.register(Venue)
class VenueAdmin(admin.ModelAdmin):
    list_display = ('title', 'city', 'max_capacity', 'price', 'status', 'placement_tariff')
    list_filter = ('status', 'placement_tariff', 'city')
    search_fields = ('title', 'address')
    filter_horizontal = ('equipment', 'amenities')

@admin.register(BookingRequest)
class BookingRequestAdmin(admin.ModelAdmin):
    list_display = ('id', 'venue', 'name', 'event_date', 'status', 'created_at')
    list_filter = ('status', 'created_at')