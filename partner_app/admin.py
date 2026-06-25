from django.contrib import admin
from .models import PartnerProfile, SalesReport, ReportSchedule


@admin.register(PartnerProfile)
class PartnerProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "company_name", "registration_type", "created_at")
    list_filter = ("registration_type",)
    search_fields = ("user__email", "company_name", "contact_person")
    readonly_fields = ("created_at", "updated_at")


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
