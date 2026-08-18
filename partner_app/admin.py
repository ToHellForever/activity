from django.contrib import admin
from django.utils.html import format_html
from .models import PartnerProfile, SalesReport, ReportSchedule, PortfolioItem, PortfolioImage, EventAccessLink


def _file_link(field_name, label):
    """Вспомогательная функция для отображения ссылки на файл."""
    def _link(obj):
        field = getattr(obj, field_name, None)
        if field:
            return format_html('<a href="{}" target="_blank">{}</a>', field.url, label or field.name)
        return "—"
    _link.short_description = label
    return _link


@admin.register(PartnerProfile)
class PartnerProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "company_name", "registration_type", "created_at")
    list_filter = ("registration_type",)
    search_fields = ("user__email", "company_name", "contact_person")
    readonly_fields = ("created_at", "updated_at")

    fieldsets = (
        ("Пользователь", {
            "fields": ("user", "registration_type"),
        }),
        ("Основная информация", {
            "fields": ("company_name", "short_name", "description"),
        }),
        ("Реквизиты", {
            "fields": ("ogrn", "inn", "kpp"),
        }),
        ("Адреса", {
            "fields": ("postal_code", "legal_address", "actual_address"),
        }),
        ("Контакты", {
            "fields": ("website", "contact_person", "phone", "email", "additional_email"),
        }),
        ("Социальные сети и ссылки", {
            "fields": ("social_links", "vk_link", "max_link", "telegram_link"),
        }),
        ("Портфолио", {
            "fields": ("cases", "reviews"),
        }),
        ("Медиафайлы", {
            "fields": ("logo", "video_business_card"),
        }),
        ("Статус обработки видео", {
            "fields": ("video_business_card_processing_status", "processed_video_business_card_hash"),
            "classes": ("collapse",),
        }),
        ("Даты", {
            "fields": ("created_at", "updated_at"),
            "classes": ("collapse",),
        }),
    )


@admin.register(SalesReport)
class SalesReportAdmin(admin.ModelAdmin):
    list_display = ("partner", "period_start", "period_end", "report_type", "status", "created_at")
    list_filter = ("report_type", "status")
    search_fields = ("partner__email",)
    readonly_fields = ("created_at",)


@admin.register(ReportSchedule)
class ReportScheduleAdmin(admin.ModelAdmin):
    list_display = ("partner", "frequency", "report_format", "is_active")
    list_filter = ("frequency", "is_active")
    search_fields = ("partner__email",)


class PortfolioImageInline(admin.TabularInline):
    """Вложенное отображение изображений портфолио."""
    model = PortfolioImage
    extra = 0
    readonly_fields = ("preview",)
    
    def preview(self, obj):
        if obj.image:
            return format_html('<img src="{}" style="max-width: 100px; border-radius: 4px;" />', obj.image.url)
        return "—"
    preview.short_description = "Превью"


@admin.register(PortfolioItem)
class PortfolioItemAdmin(admin.ModelAdmin):
    list_display = ("title", "partner", "event_date", "city", "image_count", "created_at")
    list_filter = ("event_date",)
    search_fields = ("title", "description", "partner__email")
    readonly_fields = ("created_at", "updated_at", "image_count")
    inlines = [PortfolioImageInline]
    
    fieldsets = (
        ("Основная информация", {
            "fields": ("partner", "title", "event_date", "city"),
        }),
        ("Описание", {
            "fields": ("description",),
        }),
        ("Ссылки", {
            "fields": ("links",),
            "classes": ("collapse",),
        }),
        ("Метаданные", {
            "fields": ("image_count", "created_at", "updated_at"),
            "classes": ("collapse",),
        }),
    )


@admin.register(PortfolioImage)
class PortfolioImageAdmin(admin.ModelAdmin):
    list_display = ("portfolio", "preview", "order", "created_at")
    readonly_fields = ("preview", "created_at")
    
    def preview(self, obj):
        if obj.image:
            return format_html('<img src="{}" style="max-width: 80px; border-radius: 4px;" />', obj.image.url)
        return "—"
    preview.short_description = "Превью"


@admin.register(EventAccessLink)
class EventAccessLinkAdmin(admin.ModelAdmin):
    list_display = ("name", "event", "access_code", "is_active", "scanned_count", "created_at")
    list_filter = ("is_active",)
    search_fields = ("name", "event__title", "access_code")
    readonly_fields = ("created_at", "activated_at", "deactivated_at")
    
    fieldsets = (
        ("Мероприятие", {
            "fields": ("event",),
        }),
        ("Код доступа", {
            "fields": ("name", "access_code", "is_active"),
        }),
        ("Статистика", {
            "fields": ("scanned_count",),
        }),
        ("Даты", {
            "fields": ("created_at", "activated_at", "deactivated_at"),
            "classes": ("collapse",),
        }),
    )
