from django.contrib import admin
from .models import Event, Ticket, Order, PartnerDocument, PayoutRequest, PayoutDetails
from .models import SupportTicket, SupportMessage, Tag
from .forms import EventAdminForm
from django import forms
from django.contrib import messages
from django.conf import settings
from django.conf.urls.static import static
from django.utils import timezone
from django.utils.html import mark_safe
from django.db.models import F


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


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    """
    Настройка отображения модели Tag в админке.
    """

    list_display = ("name",)
    search_fields = ("name",)
    ordering = ("name",)


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    form = EventAdminForm
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
    def get_fieldsets(self, request, obj=None):
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
                        "get_tags_display",
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

        if obj and obj.status == "rejected":
            fieldsets += (
                (
                    "Модерация",
                    {
                        "fields": ("rejection_reason",),
                    },
                ),
            )

        return fieldsets

    # Настройка отображения тегов
    def get_tags_display(self, obj):
        tags = obj.tags.all()
        if not tags:
            return "-"
        html = '<div style="display: flex; flex-wrap: wrap; gap: 5px;">'
        for tag in tags:
            html += f'<span style="background-color: #6c757d; color: white; padding: 3px 8px; border-radius: 4px; font-size: 12px;">{tag.name}</span>'
        html += "</div>"
        return mark_safe(html)

    get_tags_display.short_description = "Теги"

    # Добавляем поле для отображения статуса в виде галочки
    def get_readonly_fields(self, request, obj=None):
        return ["approved_status", "get_tags_display"]

    # Метод для отображения статуса в виде галочки
    def approved_status(self, obj):
        if obj.status == "active":
            return True
        elif obj.status == "on_moderation":
            return False
        return None

    approved_status.boolean = True
    approved_status.short_description = "Одобрено"

    # Действие для отклонения выбранных мероприятий
    def reject_events(self, request, queryset):
        if "apply" in request.POST:
            rejection_reason = request.POST.get("rejection_reason", "")
            updated = 0
            for event in queryset:
                event.status = "rejected"
                event.rejection_reason = rejection_reason
                event.save()
                self.send_rejection_notification(event, rejection_reason)
                updated += 1
            self.message_user(request, f"{updated} мероприятий отклонено.")
        else:
            return self.rejection_reason_form(request, queryset)

    reject_events.short_description = "Отклонить"

    def rejection_reason_form(self, request, queryset):
        if len(queryset) == 0:
            self.message_user(
                request, "Выберите хотя бы одно мероприятие для отклонения."
            )
            return None

        form = """
        <form method="post">
            <input type="hidden" name="action" value="reject_events">
            <input type="hidden" name="action_check" value="1">
            {% for q in queryset %}
                <input type="hidden" name="_selected_action" value="{{ q.id }}">
            {% endfor %}
            <div style="margin: 10px 0;">
                <label for="rejection_reason">Укажите причину отклонения:</label><br>
                <textarea id="rejection_reason" name="rejection_reason" rows="4" cols="60" required></textarea>
            </div>
            <input type="submit" name="apply" value="Отклонить">
        </form>
        """
        return mark_safe(form)

    def send_rejection_notification(self, event, rejection_reason):
        from django.core.mail import send_mail

        subject = f"Ваше мероприятие '{event.title}' отклонено"
        message = f"""
        Здравствуйте, {event.organizer.first_name}!

        Ваше мероприятие '{event.title}' было отклонено модератором.

        Причина отклонения: {rejection_reason}

        Пожалуйста, исправьте указанные недочеты и снова отправьте мероприятие на модерацию.

        С уважением,
        Администрация платформы
        """
        send_mail(
            subject,
            message,
            "dim.anosoff2018@yandex.ru",
            [event.organizer.email],
            fail_silently=False,
        )

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

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        return form

    def save_model(self, request, obj, form, change):
        # Проверяем, обновлены ли данные о местоположении
        place_data_field = form.data.get("place_data", "{}")
        if isinstance(place_data_field, str) and "updated" in form.data:
            obj._place_data_updated = True

        super().save_model(request, obj, form, change)


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

    list_display = ("id", "ticket", "created_at", "total_price", "is_paid")
    list_filter = ("created_at",)
    readonly_fields = ("display_qr_codes",)

    def display_qr_codes(self, obj):
        """Отображает QR-коды для заказа."""
        if not obj.qr_codes:
            return "QR-коды не сгенерированы"

        html = '<div style="display: flex; flex-wrap: wrap; gap: 10px;">'
        for qr in obj.qr_codes:
            qr_path = qr.get("qr_code_path", "")
            if qr_path:
                html += f'<div style="text-align: center;">'
                html += f'<img src="/media/{qr_path}" width="100" height="100" style="border: 1px solid #ccc;"/>'
                html += f'<div>{qr.get("unique_id", "")}</div>'
                html += f'</div>'
        html += '</div>'
        return mark_safe(html)

    display_qr_codes.short_description = "QR-коды"


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


@admin.register(PayoutRequest)
class PayoutRequestAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "organizer",
        "amount",
        "get_status_display",
        "created_at",
    )
    list_filter = ("status", "created_at")
    search_fields = ("id", "payment_details__account_holder", "organizer__email")
    readonly_fields = ("created_at",)

    # Методы для отображения данных из связанных моделей
    def get_partner_full_name(self, obj):
        return obj.organizer.get_full_name()

    get_partner_full_name.short_description = "Партнёр"

    def get_bank_name(self, obj):
        if obj.payment_details:
            return obj.payment_details.get_bank_name_display()
        return "-"

    get_bank_name.short_description = "Банк"

    def get_account_number(self, obj):
        if obj.payment_details:
            return obj.payment_details.account_number
        return "-"

    get_account_number.short_description = "Счёт/Карта"

    def get_queryset(self, request):
        # Подгружаем связанные данные одним запросом
        qs = super().get_queryset(request)
        return qs.select_related("organizer", "payment_details")

    def get_status_display(self, obj):
        return obj.get_status_display()

    get_status_display.short_description = "Статус"
