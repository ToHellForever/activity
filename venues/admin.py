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
from .forms import VenueForm, VenueImageForm


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
    form = VenueImageForm
    readonly_fields = ('image_preview',)
    extra = 0

    def image_preview(self, obj):
        if obj.image:
            return format_html('<img src="{}" style="max-height: 100px; max-width: 100px;" />', obj.image.url)
        return ""
    image_preview.short_description = "Превью"

    def get_formset(self, request, obj=None, **kwargs):
        formset = super().get_formset(request, obj, **kwargs)

        class CustomFormSet(formset):
            def delete_existing(self, obj, commit=True):
                if commit and obj.image:
                    import os
                    if os.path.isfile(obj.image.path):
                        os.remove(obj.image.path)
                super().delete_existing(obj, commit)

        return CustomFormSet

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
    filter_horizontal = ("equipment", "amenities")
    inlines = [VenueImageInline]
    change_form_template = "admin/venues/venue/change_form.html"
    fieldsets = (
        (None, {
            'fields': ('title', 'slug', 'tariff', 'status', 'venue_type', 'address', 'city', 'district', 'metro', 'latitude', 'longitude')
        }),
        ('Описание', {
            'fields': ('short_description', 'full_description')
        }),
        ('Характеристики', {
            'fields': ('area', 'max_capacity', 'price', 'price_unit')
        }),
        ('Удобства', {
            'fields': ('parking', 'has_wifi')
        }),
        ('Медиа', {
            'fields': ('video',)
        }),
        ('SEO', {
            'fields': ('meta_title', 'meta_description')
        }),
    )

    def delete_model(self, request, obj):
        # Удаляем все связанные медиафайлы
        for image in obj.images.all():
            if image.image:
                import os
                if os.path.isfile(image.image.path):
                    os.remove(image.image.path)

        if obj.video:
            import os
            if os.path.isfile(obj.video.path):
                os.remove(obj.video.path)

        # Удаляем запись из базы данных
        obj.delete()

    def delete_queryset(self, request, queryset):
        for obj in queryset:
            # Удаляем все связанные медиафайлы
            for image in obj.images.all():
                if image.image:
                    import os
                    if os.path.isfile(image.image.path):
                        os.remove(image.image.path)

            if obj.video:
                import os
                if os.path.isfile(obj.video.path):
                    os.remove(obj.video.path)

        # Удаляем записи из базы данных
        queryset.delete()

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

    def delete_queryset(self, request, queryset):
        for obj in queryset:
            if obj.video:
                import os
                if os.path.isfile(obj.video.path):
                    os.remove(obj.video.path)
        queryset.delete()
        
    def save_form(self, request, form, change):
        obj = super().save_form(request, form, change)

        # Обработка множественной загрузки фотографий при создании/редактировании площадки
        if "images" in request.FILES:
            images = request.FILES.getlist("images")
            if images:
                from django.core.exceptions import NON_FIELD_ERRORS

                try:
                    tariff = form.instance.tariff
                    limits = form.instance.TARIFF_LIMITS.get(tariff, {})
                    max_photos = limits.get("max_photos", 1)
                    current_count = VenueImage.objects.filter(
                        venue=form.instance
                    ).count()

                    for image in images:
                        if current_count >= max_photos:
                            form._errors[NON_FIELD_ERRORS] = form.error_class(
                                [
                                    f"Для тарифа {form.instance.get_tariff_display()} можно загрузить не более {max_photos} фотографий. "
                                    f"Текущее количество: {current_count}"
                                ]
                            )
                            break
                        VenueImage.objects.create(venue=form.instance, image=image)
                        current_count += 1
                except Exception as e:
                    form._errors[NON_FIELD_ERRORS] = form.error_class([str(e)])

        return obj

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)

        # Обработка очистки видео
        if 'video-clear' in request.POST:
            venue = form.instance
            if venue.video:
                import os
                if os.path.isfile(venue.video.path):
                    os.remove(venue.video.path)
                venue.video = None
                venue.save()

    def save_formset(self, request, form, formset, change):
        super().save_formset(request, form, formset, change)

        if formset.model == VenueImage:
            venue = form.instance
            tariff = venue.tariff
            limits = venue.TARIFF_LIMITS.get(tariff, {})
            max_photos = limits.get("max_photos", 1)

            # Проверяем количество фотографий после сохранения
            if VenueImage.objects.filter(venue=venue).count() > max_photos:
                raise ValidationError(
                    f"Для тарифа {venue.get_tariff_display()} можно загрузить не более {max_photos} фотографий. "
                    f"Текущее количество: {VenueImage.objects.filter(venue=venue).count()}"
                )

    class Media:
        js = ("/static/js/map_admin.js", "/static/js/venue_admin.js")


@admin.register(VenueImage)
class VenueImageAdmin(admin.ModelAdmin):
    list_display = ("venue",)
    list_filter = ("venue",)

    def delete_queryset(self, request, queryset):
        for obj in queryset:
            if obj.image:
                import os
                if os.path.isfile(obj.image.path):
                    os.remove(obj.image.path)
        queryset.delete()


@admin.register(BookingRequest)
class BookingRequestAdmin(admin.ModelAdmin):
    list_display = ("id", "venue", "name", "event_date", "status", "created_at")
    list_filter = ("status", "created_at")
