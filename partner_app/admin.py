from django.contrib import admin
from django.utils.html import format_html
from .models import PartnerProfile, SalesReport, ReportSchedule


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
            "fields": ("legal_address", "actual_address"),
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
