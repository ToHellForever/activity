from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import Event, Ticket, Order, PartnerDocument, PayoutRequest, PayoutDetails
from .models import SupportTicket, SupportMessage, Tag, EventPackage, MainTag, UserPackageSubscription
from .proxy_models import EventRequestProxy
from .forms import EventAdminForm
from django import forms
from django.contrib import messages
from django.conf import settings
from django.conf.urls.static import static
from django.utils import timezone
from django.utils.html import mark_safe
from django.db.models import F, Count
from django.contrib.auth import get_user_model

CustomUser = get_user_model()

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

@admin.register(MainTag)
class MainTagAdmin(admin.ModelAdmin):
    """
    Настройка отображения модели MainTag в админке.
    """

    list_display = ("name",)
    search_fields = ("name",)
    ordering = ("name",)

@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    """
    Настройка отображения модели Tag в админке.
    """

    list_display = ("name", "main_tag")
    list_filter = ("main_tag",)
    search_fields = ("name", "main_tag__name")
    ordering = ("main_tag__name", "name",)

class TicketInline(admin.TabularInline):
    model = Ticket
    extra = 1
    fields = ('name', 'price', 'available_quantity', 'get_sold_count', 'get_available_count')
    readonly_fields = ('get_sold_count', 'get_available_count')

    def get_queryset(self, request):
        """Оптимизируем загрузку связанных заказов для всех билетов."""
        queryset = super().get_queryset(request)
        return queryset.prefetch_related('orders')

    def get_sold_count(self, obj):
        """Возвращает количество проданных билетов."""
        if obj.pk:
            return sum(order.quantity for order in obj.orders.exclude(payment_status="refunded"))
        return 0

    def get_available_count(self, obj):
        """Возвращает количество доступных билетов."""
        if obj.pk:
            sold = sum(order.quantity for order in obj.orders.exclude(payment_status="refunded"))
            return obj.available_quantity - sold
        return 0

    get_sold_count.short_description = "Продано"
    get_available_count.short_description = "Доступно"

@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    inlines = [TicketInline]
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

    def get_queryset(self, request):
        """Оптимизируем загрузку связанных данных для списка мероприятий."""
        queryset = super().get_queryset(request)
        return queryset.select_related('organizer', 'category', 'package').prefetch_related('tags', 'images')

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
                        "allow_platform_requests",
                        "commission_rate",
                        "auto_close_sales_hours",
                    )
                },
            ),
            # Добавляем блок для отображения фотографий
            (
                "Фотографии мероприятия",
                {
                    "fields": ("get_images_display",),
                    "description": "Все фотографии, загруженные для мероприятия (основное изображение и дополнительные фотографии)",
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

    # Настройка отображения фотографий мероприятия
    def get_images_display(self, obj):
        """Отображает все фотографии мероприятия, включая основное изображение и фотографии из EventImage."""
        images_html = ""

        # Основное изображение
        if obj.image:
            images_html += f'<div style="margin: 5px; display: inline-block;">'
            images_html += f'<img src="{obj.image.url}" style="max-width: 200px; max-height: 200px; border: 1px solid #ddd; padding: 5px;">'
            images_html += f'<div style="text-align: center; font-size: 12px;">Основное изображение</div>'
            images_html += f'</div>'

        # Дополнительные фотографии из EventImage
        event_images = obj.images.all()
        if event_images:
            for img in event_images:
                images_html += f'<div style="margin: 5px; display: inline-block;">'
                images_html += f'<img src="{img.image.url}" style="max-width: 200px; max-height: 200px; border: 1px solid #ddd; padding: 5px;">'
                images_html += f'<div style="text-align: center; font-size: 12px;">Дополнительное фото</div>'
                images_html += f'</div>'

        if not images_html:
            return "Нет фотографий"

        return mark_safe(f'<div style="display: flex; flex-wrap: wrap;">{images_html}</div>')

    get_images_display.short_description = "Фотографии мероприятия"

    # Добавляем поле для отображения статуса в виде галочки
    def get_readonly_fields(self, request, obj=None):
        readonly_fields = ["approved_status", "get_tags_display"]
        # Добавляем отображение фотографий только для существующих объектов
        if obj:
            readonly_fields.append("get_images_display")
        return readonly_fields

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
        """Оптимизируем загрузку связанных данных для формы редактирования."""
        form = super().get_form(request, obj, **kwargs)

        # Если редактируется существующее мероприятие, оптимизируем загрузку связанных данных
        if obj:
            # Загружаем все связанные данные заранее
            obj.tags.prefetch_related(None)  # Сбрасываем предыдущий prefetch
            obj.tickets.prefetch_related('orders').all()  # Загружаем билеты с заказами
            obj.images.all()  # Загружаем фотографии мероприятия

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

class SubscriptionInline(admin.TabularInline):
    model = UserPackageSubscription
    extra = 0
    readonly_fields = ('package', 'start_date', 'end_date', 'is_active')

    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

@admin.register(SupportTicket)
class SupportTicketAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "subject",
        "status",
        "created_at",
        "get_ticket_type",
    )
    list_filter = ("status", "created_at")
    readonly_fields = ("user", "subject", "created_at", "event")
    fieldsets = (
        (None, {"fields": ("user", "status")}),
        ("Тикет", {"fields": ("subject", "created_at")}),
    )

    def get_ticket_type(self, obj):
        if obj.event:
            return "Заявка на мероприятие"
        return "Обычный тикет"

    get_ticket_type.short_description = "Тип тикета"

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.filter(event__isnull=True)

@admin.register(EventRequestProxy)
class EventRequestAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "event",
        "status",
        "created_at",
        "get_event_title",
        "get_user_question",
    )
    list_filter = ("status", "created_at", "event")
    readonly_fields = (
        "user",
        "subject",
        "created_at",
        "event",
        "get_user_question_display",
    )

    def get_event_title(self, obj):
        return obj.event.title if obj.event else "-"

    get_event_title.short_description = "Мероприятие"

    def get_user_question(self, obj):
        first_message = obj.messages.first()
        if first_message and first_message.text:
            return first_message.text.replace("Вопрос от участника:\n", "").strip()
        return "-"

    get_user_question.short_description = "Вопрос участника"

    def get_user_question_display(self, obj):
        return self.get_user_question(obj)

    get_user_question_display.short_description = "Вопрос участника"

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return (
            qs.filter(event__isnull=False)
            .select_related("event")
            .prefetch_related("messages")
        )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

class EventRequestAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "event", "status", "created_at", "get_event_title")
    list_filter = ("status", "created_at", "event")
    readonly_fields = ("user", "subject", "created_at", "event")

    def get_event_title(self, obj):
        return obj.event.title if obj.event else "-"

    get_event_title.short_description = "Мероприятие"

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.filter(event__isnull=False).select_related("event")

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_model_perms(self, request):
        return {}

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

@admin.register(EventPackage)
class EventPackageAdmin(admin.ModelAdmin):
    """Настройка отображения пакетов мероприятий в админке."""

    list_display = (
        "name",
        "price",
        "max_active_events",
        "event_card_type",
        "description_type",
        "has_video",
        "has_program_and_speakers",
        "max_photos",
        "visibility_level",
    )

    list_filter = (
        "event_card_type",
        "description_type",
        "has_video",
        "has_program_and_speakers",
        "visibility_level",
    )

    search_fields = ("name",)

    fieldsets = (
        (
            None,
            {
                "fields": (
                    "name",
                    "price",
                    "max_active_events",
                )
            },
        ),
        (
            "Настройки отображения",
            {
                "fields": (
                    "event_card_type",
                    "description_type",
                    "visibility_level",
                )
            },
        ),
        (
            "Функциональные возможности",
            {
                "fields": (
                    "has_program_and_speakers",
                    "max_photos",
                    "has_video",
                    "has_platform_request",
                    "has_free_registration",
                    "has_ticket_sales",
                    "has_collection_participation",
                )
            },
        ),
    )

# Кастомная админка для партнёров
class PartnerSubscriptionInline(admin.TabularInline):
    model = UserPackageSubscription
    extra = 0
    readonly_fields = ('package', 'start_date', 'end_date', 'is_active')

    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

class PartnerEventInline(admin.TabularInline):
    model = Event
    extra = 0
    readonly_fields = ('title', 'status', 'date_time', 'package')
    fields = ('title', 'status', 'date_time', 'package')

    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

class PartnerPayoutInline(admin.TabularInline):
    model = PayoutRequest
    extra = 0
    readonly_fields = ('amount', 'status', 'created_at')

    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

@admin.register(CustomUser)
class PartnerAdmin(admin.ModelAdmin):
    """
    Кастомная админка для партнёров с полной информацией о подписках, пакетах и активности.
    """

    list_display = (
        'username', 'email', 'company_name', 'contact_person',
        'phone_number', 'has_active_subscription', 'get_active_subscriptions', 'get_total_purchases'
    )

    list_filter = (
        'user_type',
        'is_verified',
        'verification_status',
    )

    search_fields = (
        'username', 'email', 'company_name', 'contact_person', 'phone_number'
    )

    inlines = [PartnerSubscriptionInline, PartnerEventInline, PartnerPayoutInline]

    fieldsets = (
        (None, {
            'fields': ('username', 'email', 'first_name', 'last_name')
        }),
        ('Компания', {
            'fields': ('company_name', 'contact_person', 'phone_number', 'logo', 'social_links')
        }),
        ('Статус', {
            'fields': ('user_type', 'is_verified', 'verification_status')
        }),
        ('Видео-визитка', {
            'fields': ('video_business_card', 'video_business_card_processing_status')
        }),
    )

    def get_active_subscriptions(self, obj):
        """Возвращает количество активных подписок партнёра"""
        return obj.userpackagesubscription_set.filter(is_active=True).count()
    get_active_subscriptions.short_description = "Активные подписки"

    def has_active_subscription(self, obj):
        """Возвращает визуальный индикатор активной подписки (галочка/крестик)"""
        has_active = obj.userpackagesubscription_set.filter(is_active=True).exists()
        if has_active:
            return mark_safe('<span style="color: green; font-weight: bold;">✓</span>')
        else:
            return mark_safe('<span style="color: red; font-weight: bold;">✗</span>')
    has_active_subscription.short_description = "Активная подписка"
    has_active_subscription.allow_tags = True

    def get_total_purchases(self, obj):
        """Возвращает общее количество покупок пакетов"""
        return obj.userpackagesubscription_set.count()
    get_total_purchases.short_description = "Всего покупок"

    def get_queryset(self, request):
        """Фильтруем только партнёров"""
        qs = super().get_queryset(request)
        return qs.filter(user_type='partner').prefetch_related(
            'userpackagesubscription_set',
            'event_set',
            'payoutrequest_set'
        )

    def get_inline_instances(self, request, obj=None):
        """Показываем инлайны только для партнёров"""
        if obj and obj.user_type == 'partner':
            return super().get_inline_instances(request, obj)
        return []

# Создаем прокси-модель для не-партнёров
class NonPartnerUser(CustomUser):
    class Meta:
        proxy = True
        verbose_name = "Не-партнёр"
        verbose_name_plural = "Не-партнёры"

# Кастомная админка для не-партнёров (гости и посетители)
@admin.register(NonPartnerUser)
class NonPartnerAdmin(admin.ModelAdmin):
    """
    Кастомная админка для пользователей, которые не являются партнёрами.
    """

    list_display = (
        'username', 'email', 'first_name', 'last_name',
        'user_type', 'is_verified', 'verification_status'
    )

    list_filter = (
        'user_type',
        'is_verified',
        'verification_status',
    )

    search_fields = (
        'username', 'email', 'first_name', 'last_name'
    )

    fieldsets = (
        (None, {
            'fields': ('username', 'email', 'first_name', 'last_name')
        }),
        ('Статус', {
            'fields': ('user_type', 'is_verified', 'verification_status')
        }),
    )

    def get_queryset(self, request):
        """Фильтруем только не-партнёров"""
        qs = super().get_queryset(request)
        return qs.exclude(user_type='partner')

    def get_inline_instances(self, request, obj=None):
        """Не показываем инлайны для не-партнёров"""
        return []

# Регистрируем модели, которые ещё не зарегистрированы
try:
    admin.site.unregister(CustomUser)
except:
    pass

# Регистрируем админку для партнёров
admin.site.register(CustomUser, PartnerAdmin)

# Регистрируем подписки на пакеты
@admin.register(UserPackageSubscription)
class UserPackageSubscriptionAdmin(admin.ModelAdmin):
    """
    Админка для управления подписками пользователей на пакеты.
    """

    list_display = ('user', 'package', 'start_date', 'end_date', 'is_active')
    list_filter = ('is_active', 'package', 'start_date')
    search_fields = ('user__username', 'user__email', 'package__name')

    readonly_fields = ('start_date', 'end_date')

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False