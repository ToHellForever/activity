from django.contrib import admin
from django.utils.html import format_html
from .models import SalesReport, ReportSchedule, PortfolioItem, PortfolioImage, EventAccessLink


def _file_link(field_name, label):
    """Вспомогательная функция для отображения ссылки на файл."""
    def _link(obj):
        field = getattr(obj, field_name, None)
        if field:
            return format_html('<a href="{}" target="_blank">{}</a>', field.url, label or field.name)
        return "—"
    _link.short_description = label
    return _link


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

    def delete_queryset(self, request, queryset):
        for obj in queryset:
            if obj.image:
                obj.image.delete(save=False)
            obj.delete()


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
