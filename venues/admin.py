from django.contrib import admin
from django.utils.html import format_html
from django.core.exceptions import ValidationError
from django.db.models import Count
from django.shortcuts import get_object_or_404
from django.template.response import TemplateResponse
from django.urls import path
from .models import (
    VenueType,
    Venue,
    BookingRequest,
    VenueAdditionRequest,
    VenueImage,
    VenueView,
    EquipmentCategory,
    EquipmentItem,
    VenueFormat,
)
from .forms import VenueForm, VenueImageForm
import os

class EquipmentItemInline(admin.TabularInline):
    model = EquipmentItem
    extra = 1
    fields = ("name",)


@admin.register(EquipmentCategory)
class EquipmentCategoryAdmin(admin.ModelAdmin):
    list_display = ("name",)
    search_fields = ("name",)
    ordering = ("name",)
    list_per_page = 20
    inlines = [EquipmentItemInline]


@admin.register(EquipmentItem)
class EquipmentItemAdmin(admin.ModelAdmin):
    list_display = ("name", "category")
    search_fields = ("name", "category__name")
    list_filter = ("category",)
    ordering = ("category__name", "name")
    list_per_page = 20


@admin.register(VenueType)
class VenueTypeAdmin(admin.ModelAdmin):
    list_display = ("name",)


class VenueImageInline(admin.TabularInline):
    model = VenueImage
    form = VenueImageForm
    readonly_fields = ("image_preview",)
    extra = 0

    def image_preview(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" style="max-height: 100px; max-width: 100px;" />',
                obj.image.url,
            )
        return ""

    image_preview.short_description = "Превью"

    def get_formset(self, request, obj=None, **kwargs):
        formset = super().get_formset(request, obj, **kwargs)

        class CustomFormSet(formset):
            def delete_existing(self, obj, commit=True):
                if commit and obj.image:
                    try:
                        if os.path.isfile(obj.image.path):
                            os.remove(obj.image.path)
                    except NotImplementedError:
                        obj.image.delete(save=False)
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
        "views_total",
    )
    list_filter = ("status", "tariff", "city", "venue_type")
    search_fields = ("title", "address")
    inlines = [VenueImageInline]
    change_form_template = "admin/venues/venue/change_form.html"
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "title",
                    "slug",
                    "tariff",
                    "status",
                    "venue_type",
                    "address",
                    "city",
                    "district",
                    "metro",
                    "latitude",
                    "longitude",
                )
            },
        ),
        ("Описание", {"fields": ("description",)}),
        ("Характеристики", {"fields": ("area", "max_capacity", "price", "price_unit")}),
        ("Оборудование и удобства", {"fields": ("equipment", "formats")}),
        ("Медиа", {"fields": ("video",)}),
        ("Контакты", {"fields": ("contact_info", "email")}),
        ("SEO", {"fields": ("meta_title", "meta_description")}),
    )

    def delete_model(self, request, obj):
        for image in obj.images.all():
            if image.image:
                try:
                    if os.path.isfile(image.image.path):
                        os.remove(image.image.path)
                except NotImplementedError:
                    image.image.delete(save=False)

        if obj.video:
            try:
                if os.path.isfile(obj.video.path):
                    os.remove(obj.video.path)
            except NotImplementedError:
                obj.video.delete(save=False)

        obj.delete()

    def delete_queryset(self, request, queryset):
        for obj in queryset:
            for image in obj.images.all():
                if image.image:
                    try:
                        if os.path.isfile(image.image.path):
                            os.remove(image.image.path)
                    except NotImplementedError:
                        image.image.delete(save=False)

            if obj.video:
                try:
                    if os.path.isfile(obj.video.path):
                        os.remove(obj.video.path)
                except NotImplementedError:
                    obj.video.delete(save=False)

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

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)

        images = request.FILES.getlist("images")
        if images:
            venue = form.instance
            limits = venue.TARIFF_LIMITS.get(venue.tariff, {})
            max_photos = limits.get("max_photos", 1)
            current_count = VenueImage.objects.filter(venue=venue).count()
            for image in images:
                if current_count >= max_photos:
                    raise ValidationError(
                        f"Для тарифа {venue.get_tariff_display()} можно загрузить не более {max_photos} фотографий."
                    )
                VenueImage.objects.create(venue=venue, image=image)
                current_count += 1

        if "video-clear" in request.POST:
            venue = form.instance
            if venue.video:
                try:
                    if os.path.isfile(venue.video.path):
                        os.remove(venue.video.path)
                except NotImplementedError:
                    venue.video.delete(save=False)
                venue.video = None
                venue.save()

    def save_form(self, request, form, change):
        obj = super().save_form(request, form, change)

        # Проверяем лимит до сохранения Venue, а сами фото создаём после его save().
        images = request.FILES.getlist("images")
        if images:
            limits = obj.TARIFF_LIMITS.get(obj.tariff, {})
            max_photos = limits.get("max_photos", 1)
            current_count = VenueImage.objects.filter(venue=obj).count() if obj.pk else 0
            if current_count + len(images) > max_photos:
                form.add_error(
                    None,
                    f"Для тарифа {obj.get_tariff_display()} можно загрузить не более {max_photos} фотографий. "
                    f"Текущее количество: {current_count}.",
                )

        return obj

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
        js = (
            "/static/js/venue_admin.js",
            "/static/js/equipment_admin.js",
        )

    # ===== Статистика переходов =====

    @admin.display(description="Переходы (всего)")
    def views_total(self, obj):
        """Всего переходов на страницу площадки (за всё время)."""
        return obj.views.count()

    views_total.admin_order_field = "views_count"

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(
            views_count=Count("views"),
        )

    def get_urls(self):
        """Добавляем страницу статистики переходов: /admin/venues/venue/<id>/views/."""
        urls = super().get_urls()
        custom_urls = [
            path(
                "<int:venue_id>/views/",
                self.admin_site.admin_view(self.views_report),
                name="venues_venue_views",
            ),
            path(
                "views-report/",
                self.admin_site.admin_view(self.views_report),
                name="venues_views_report",
            ),
        ]
        return custom_urls + urls

    def views_report(self, request, venue_id=None):
        """
        Отчёт по переходам на площадки за выбранный период.

        Без venue_id — сводка по всем площадкам;
        с venue_id — детальная статистика по одной площадке (по дням,
        уникальные посетители, источники переходов).
        """
        from django.db.models.functions import TruncDate
        from django.utils import timezone as dj_timezone
        from datetime import datetime, timedelta, date as date_cls

        period_start = request.GET.get("period_start", "")
        period_end = request.GET.get("period_end", "")

        def parse_date(value):
            try:
                return datetime.strptime(value, "%d.%m.%Y").date()
            except (ValueError, TypeError):
                return None

        start = parse_date(period_start)
        end = parse_date(period_end)
        # Период по умолчанию — последние 30 дней
        if not start and not end:
            end = dj_timezone.now().date()
            start = end - timedelta(days=29)
        elif start and not end:
            end = start + timedelta(days=29)
        elif end and not start:
            start = end - timedelta(days=29)

        qs = VenueView.objects.filter(viewed_at__date__range=[start, end])
        if venue_id:
            venue = get_object_or_404(Venue, pk=venue_id)
            qs = qs.filter(venue=venue)
        else:
            venue = None

        context = {
            **self.admin_site.each_context(request),
            "title": (
                f"Переходы на «{venue.title}»" if venue else "Отчёт по переходам на площадки"
            ),
            "venue": venue,
            "period_start": start.strftime("%d.%m.%Y"),
            "period_end": end.strftime("%d.%m.%Y"),
            "total_views": qs.count(),
            "unique_visitors": qs.values("session_key", "user").distinct().count(),
            # Сводка по всем площадкам (только для общего отчёта)
            "venues_summary": None,
            # Детализация по дням (только для одной площадки)
            "daily_stats": None,
            "sources_stats": None,
            "opts": Venue._meta,
        }

        if venue:
            daily = (
                qs.annotate(day=TruncDate("viewed_at"))
                .values("day")
                .annotate(views=Count("id"))
                .order_by("day")
            )
            daily_stats = [
                {
                    "day": item["day"].strftime("%d.%m.%Y"),
                    "views": item["views"],
                }
                for item in daily
            ]
            context["daily_stats"] = daily_stats
            context["max_daily_views"] = max(
                (item["views"] for item in daily_stats), default=1
            )
            sources = (
                qs.values("source")
                .annotate(views=Count("id"))
                .order_by("-views")[:10]
            )
            context["sources_stats"] = [
                {
                    "source": item["source"] or "(прямой переход)",
                    "views": item["views"],
                }
                for item in sources
            ]
        else:
            summary = (
                qs.values("venue__id", "venue__title")
                .annotate(views=Count("id"))
                .order_by("-views")[:50]
            )
            context["venues_summary"] = [
                {
                    "venue_id": item["venue__id"],
                    "title": item["venue__title"],
                    "views": item["views"],
                }
                for item in summary
            ]

        return TemplateResponse(
            request, "admin/venues/venue/views_report.html", context
        )


@admin.register(VenueImage)
class VenueImageAdmin(admin.ModelAdmin):
    list_display = ("venue",)
    list_filter = ("venue",)

    def delete_queryset(self, request, queryset):
        for obj in queryset:
            if obj.image:
                try:
                    if os.path.isfile(obj.image.path):
                        os.remove(obj.image.path)
                except NotImplementedError:
                    obj.image.delete(save=False)
        queryset.delete()


@admin.register(VenueView)
class VenueViewAdmin(admin.ModelAdmin):
    """Журнал переходов на площадки — только просмотр и фильтры."""

    list_display = ("venue", "viewed_at", "user", "session_key", "source")
    list_filter = ("venue", "viewed_at")
    search_fields = ("venue__title", "source", "session_key")
    readonly_fields = ("venue", "viewed_at", "user", "session_key", "source")
    date_hierarchy = "viewed_at"
    list_select_related = ("venue", "user")


@admin.register(BookingRequest)
class BookingRequestAdmin(admin.ModelAdmin):
    list_display = ("id", "venue", "name", "phone", "user", "event_date", "status", "created_at")
    list_filter = ("status", "created_at", "venue")
    search_fields = ("name", "phone", "email", "venue__title")
    readonly_fields = ("created_at",)
    list_select_related = ("venue", "user")


@admin.register(VenueAdditionRequest)
class VenueAdditionRequestAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "venue_name",
        "applicant_name",
        "applicant_phone",
        "applicant_email",
        "status",
        "created_at",
    )
    list_filter = ("status", "created_at")
    search_fields = (
        "venue_name",
        "address",
        "applicant_name",
        "applicant_phone",
        "applicant_email",
    )
    readonly_fields = ("created_at",)
    list_select_related = ("user",)


@admin.register(VenueFormat)
class VenueFormatAdmin(admin.ModelAdmin):
    list_display = ("name",)
    search_fields = ("name",)
    ordering = ("name",)
