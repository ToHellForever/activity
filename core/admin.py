from django.contrib import admin
from .models import Event, Ticket, Order, PartnerDocument
from .models import SupportTicket, SupportMessage
from django import forms
from django.contrib import messages
from django.conf import settings
from django.conf.urls.static import static
from django.utils import timezone
from django.utils.html import mark_safe


@admin.register(PartnerDocument)
class PartnerDocumentAdmin(admin.ModelAdmin):
    """
    Админка для управления документами партнёров.
    """

    list_display = ("user", "document", "uploaded_at", "is_approved", "reviewer")
    list_filter = ("is_approved", "uploaded_at")
    search_fields = ("user__username", "user__company_name")
    readonly_fields = ("uploaded_at",)

    fieldsets = (
        (None, {"fields": ("user", "document", "uploaded_at")}),
        ("Модерация", {"fields": ("is_approved", "reviewer", "reviewed_at")}),
    )

    def save_model(self, request, obj, form, change):
        if change:
            # Если статус изменился на "подтверждено", обновляем статус пользователя
            if obj.is_approved and not obj.reviewed_at:
                obj.reviewed_at = timezone.now()
                obj.reviewer = request.user
                obj.user.is_verified = True
                obj.user.verification_status = "approved"
                obj.user.save()
            elif not obj.is_approved and obj.reviewed_at:
                obj.user.verification_status = "rejected"
                obj.user.save()
            else:
                # Если документы только что загружены, устанавливаем статус "на рассмотрении"
                obj.user.verification_status = "pending"
                obj.user.save()
            super().save_model(request, obj, form, change)


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    """
    Настройка отображения модели Event в админке.
    """

    # Какие поля показывать в списке всех мероприятий
    list_display = (
        "title",
        "organizer",
        "date_time",
        "get_duration",
        "status",
        "commission_rate",
    )

    def get_duration(self, obj):
        if obj.duration:
            return obj.duration
        return "-"

    get_duration.short_description = "Длительность"

    # По каким полям можно фильтровать список
    list_filter = (
        "status",
        "date_time",
        "category",
    )

    # Какие поля использовать для поиска
    search_fields = ("title", "organizer__username")

    # Добавляем действия для пакетного изменения статусов
    actions = [
        "reject_events",
        "to_moderation",
        "to_active",
        "to_completed",
    ]

    # Группировка полей на странице редактирования
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "title",
                    "organizer",
                    "description_short",
                    "description_full",
                    "date_time",
                    "duration",
                    "place_data",
                )
            },
        ),
        ("Медиа и Файлы", {"fields": ("image", "video_url", "program_file")}),
        (
            "Настройки и Категории",
            {
                "fields": (
                    "status",
                    "category",
                    "tags",
                    "allow_booking_without_payment",
                    "commission_rate",
                    "auto_close_sales_hours",
                )
            },
        ),
        # Добавляем блок для отображения статуса
        (
            "Статусы",
            {
                "fields": ("approved_status",),
            },
        ),
    )

    # Добавляем поле для отображения статуса в виде галочки
    readonly_fields = ("approved_status",)

    # Метод для отображения статуса в виде галочки
    def approved_status(self, obj):
        if obj.status == "active":
            return True
        elif obj.status == "on_moderation":
            return False
        return None

    approved_status.boolean = True
    approved_status.short_description = "Одобрено"

    # Действие для одобрения выбранных мероприятий

    # Действие для отклонения выбранных мероприятий
    def reject_events(self, request, queryset):
        updated = queryset.update(status="rejected")
        self.message_user(request, f"{updated} мероприятий отклонено.")

    reject_events.short_description = "Отклонить"

    # Действие для установки статуса "На модерации"
    def to_moderation(self, request, queryset):
        updated = queryset.update(status="on_moderation")
        self.message_user(request, f"{updated} мероприятий переведено на модерацию.")

    to_moderation.short_description = "На модерации"

    # Действие для установки статуса "Активно"
    def to_active(self, request, queryset):
        updated = queryset.update(status="active")
        self.message_user(request, f"{updated} мероприятий активировано.")

    to_active.short_description = "Активно"

    # Действие для установки статуса "Завершено"
    def to_completed(self, request, queryset):
        updated = queryset.update(status="completed")
        self.message_user(request, f"{updated} мероприятий помечено как завершённые.")

    to_completed.short_description = "Завершено"


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    """
    Настройка отображения типов билетов.
    """

    list_display = (
        "name",
        "event",
        "price",
        "available_quantity",
        "get_sold_count",
        "get_available_count",
    )
    search_fields = ("name", "event__title")

    def get_sold_count(self, obj):
        """Возвращает количество проданных билетов."""
        return sum(order.quantity for order in obj.orders.all())

    get_sold_count.short_description = "Продано"

    def get_available_count(self, obj):
        """Возвращает количество доступных билетов."""
        return obj.get_available_count()

    get_available_count.short_description = "Доступно"


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    """
    Настройка отображения заказов.
    """

    list_display = ("id", "ticket", "created_at", "total_price")
    list_filter = ("created_at",)


# --- Регистрация модели пользователя (если нужна кастомизация) ---
# Если тебя устраивает стандартное отображение CustomUser, это можно пропустить.
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth import get_user_model

CustomUser = get_user_model()


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    """
    Настройка отображения нашей кастомной модели пользователя.
    """

    list_display = UserAdmin.list_display + (
        "user_type",
        "is_verified",
        "verification_status",
    )
    list_filter = UserAdmin.list_filter + (
        "user_type",
        "is_verified",
        "verification_status",
    )
    fieldsets = (("Видео-визитка", {"fields": ("video_business_card",)}),)


@admin.register(SupportTicket)
class SupportTicketAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "subject", "status", "created_at")
    list_filter = ("status", "created_at")
    readonly_fields = ("user", "subject", "created_at")
    fieldsets = (
        (None, {"fields": ("user", "status")}),
        ("Тикет", {"fields": ("subject", "created_at")}),
    )
