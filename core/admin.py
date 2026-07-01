from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import Event, Ticket, Order, PartnerDocument, PayoutRequest, PayoutDetails
from .models import SupportTicket, SupportMessage, Tag, EventPackage, MainTag, UserPackageSubscription, Category, Format
from .proxy_models import EventRequestProxy, VisitorUser
from .forms import EventAdminForm, PartnerAdminForm
from django import forms
from django.contrib import messages
from django.conf import settings
from django.conf.urls.static import static
from django.utils import timezone
from django.utils.html import mark_safe
from django.db.models import F, Count
from django.contrib.auth import get_user_model
from django.shortcuts import render

CustomUser = get_user_model()

@admin.register(VisitorUser)
class VisitorUserAdmin(admin.ModelAdmin):
    """
    Админ-панель для управления обычными пользователями (не партнёрами).
    """
    
    list_display = ('username', 'email', 'first_name', 'last_name', 'date_joined', 'is_active')
    search_fields = ('username', 'email')
    list_filter = ('is_active', 'date_joined')

    def get_queryset(self, request):
        """
        Возвращает только тех пользователей, которые НЕ являются партнёрами.
        """
        # Получаем базовый QuerySet
        qs = super().get_queryset(request)

        return qs.exclude(user_type='partner') 

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

@admin.register(PayoutDetails)
class PayoutDetailsAdmin(admin.ModelAdmin):
    """
    Админка для управления реквизитами для выплат.
    """

    list_display = ("partner",)
    
@admin.register(PartnerDocument)
class PartnerDocumentAdmin(admin.ModelAdmin):
    """
    Админка для управления документами партнёров.
    """

    list_display = ("user", "document", "uploaded_at", "is_approved", "reviewer", "get_status")
    list_filter = ("is_approved", "uploaded_at")
    search_fields = ("user__username", "user__company_name", "user__email")
    readonly_fields = ("uploaded_at",)

    def get_fieldsets(self, request, obj=None):
        if obj and not obj.is_approved and obj.rejection_reason:
            return (
                (None, {"fields": ("user", "document", "uploaded_at")}),
                ("Модерация", {"fields": ("is_approved", "reviewer", "reviewed_at")}),
                ("Причина отклонения", {"fields": ("rejection_reason",)}),
            )
        return (
            (None, {"fields": ("user", "document", "uploaded_at")}),
            ("Модерация", {"fields": ("is_approved", "reviewer", "reviewed_at", "rejection_reason")}),
        )

    def get_status(self, obj):
        if obj.is_approved:
            return mark_safe('<span style="color: green; font-weight: bold;">✓ Подтверждён</span>')
        elif obj.rejection_reason:
            return mark_safe('<span style="color: red; font-weight: bold;">✗ Отклонён</span>')
        return mark_safe('<span style="color: orange;">На проверке</span>')
    get_status.short_description = "Статус"

    def save_model(self, request, obj, form, change):
        from django.core.mail import send_mail
        from django.conf import settings

        is_new_approval = change and obj.is_approved and not obj.reviewed_at
        is_rejection = change and not obj.is_approved and obj.reviewed_at
        
        # Сохраняем объект
        super().save_model(request, obj, form, change)
 
        # Обновляем статус пользователя и отправляем уведомления
        if is_new_approval:
            # Документ только что одобрен
            obj.reviewed_at = timezone.now()
            obj.reviewer = request.user
            obj.save(update_fields=['reviewed_at', 'reviewer'])
            
            obj.user.is_verified = True
            obj.user.verification_status = "approved"
            obj.user.save(update_fields=['is_verified', 'verification_status'])
            
            # Отправляем уведомление партнёру
            try:
                send_mail(
                    subject='Ваши документы подтверждены',
                    message=f'''Здравствуйте, {obj.user.get_full_name()}!

Ваши документы успешно проверены. Ваш статус: Подтверждённый организатор ✓

Теперь вы можете использовать все возможности платформы.

С уважением,
Администрация платформы''',
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[obj.user.email],
                    fail_silently=False,
                )
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Не удалось отправить email об одобрении: {e}")
                
        elif is_rejection:
            # Документ отклонён
            obj.user.verification_status = "rejected"
            obj.user.save(update_fields=['verification_status'])
            
            # Отправляем уведомление с причиной
            reason_text = obj.rejection_reason or "Причина не указана"
            try:
                send_mail(
                    subject='Ваши документы отклонены',
                    message=f'''Здравствуйте, {obj.user.get_full_name()}!

Ваши документы были отклонены модератором.

Причина отклонения: {reason_text}

Пожалуйста, исправьте указанные недочёты и загрузите документы повторно.

С уважением,
Администрация платформы''',
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[obj.user.email],
                    fail_silently=False,
                )
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Не удалось отправить email об отклонении: {e}")

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
            return sum(order.quantity for order in obj.orders.exclude(payment_status__in=["refunded", "canceled"]))
        return 0

    def get_available_count(self, obj):
        """Возвращает количество доступных билетов."""
        sold = sum(order.quantity for order in obj.orders.exclude(payment_status__in=["refunded", "canceled"]))
        return obj.available_quantity - sold

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
        "format",
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
                        "description",
                        "date_time",
                        "duration",
                        "address",
                        "city",
                        "district",
                        "metro",
                        "latitude",
                        "longitude",
                        "additional_adress",
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
                        "format",
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
            settings.DEFAULT_FROM_EMAIL,
            [event.organizer.email],
            fail_silently=False,
        )

    # Действие для установки статуса "На модерации"
    def to_moderation(self, request, queryset):
        for event in queryset:
            self._check_active_events_limit(request, event)
        updated = queryset.update(status="on_moderation")
        self.message_user(request, f"{updated} мероприятий переведено на модерацию.")

    to_moderation.short_description = "На модерации"

    # Действие для установки статуса "Активно"
    def to_active(self, request, queryset):
        for event in queryset:
            self._check_active_events_limit(request, event, is_activating=True)
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

        form.base_fields['description'].required = False

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

        # Сохраняем оригинальный статус для сравнения
        original_status = None
        if change and obj.pk:
            original_event = Event.objects.get(pk=obj.pk)
            original_status = original_event.status

        # Проверяем ограничение на количество активных мероприятий только при изменении статуса
        if (obj.status in ["active", "on_moderation"] and
            (not change or (change and original_status != obj.status))):
            self._check_active_events_limit(request, obj, original_status)

        super().save_model(request, obj, form, change)
 
    def _check_active_events_limit(self, request, event, original_status=None, is_activating=False):
        """Проверяет, не превышает ли количество активных мероприятий лимит пакета."""
        from .models import Event

        # Если это существующее мероприятие и статус не меняется, пропускаем проверку
        if event.pk and original_status == event.status:
            return

        # Получаем активную подписку пользователя
        active_subscription = event.organizer.userpackagesubscription_set.filter(is_active=True).first()
        if not active_subscription:
            self.message_user(
                request,
                f"У пользователя {event.organizer.username} нет активной подписки на пакет.",
                level=messages.ERROR
            )
            raise forms.ValidationError("У пользователя нет активной подписки на пакет.")

        # Получаем пакет пользователя
        package = event.package or active_subscription.package
        if not package:
            self.message_user(
                request,
                f"У пользователя {event.organizer.username} не выбран пакет.",
                level=messages.ERROR
            )
            raise forms.ValidationError("У пользователя не выбран пакет.")

        # Считаем количество ТОЛЬКО активных мероприятий (status="active")
        active_events_count = Event.objects.filter(
            organizer=event.organizer,
            status="active"
        ).exclude(pk=event.pk).count()

        # Если это активация мероприятия (перевод в статус "active"), учитываем его в лимитах
        if is_activating or event.status == "active":
            active_events_count += 1

        # Проверяем не превышает ли количество активных мероприятий лимит пакета
        if active_events_count > package.max_active_events:
            self.message_user(
                request,
                f"У пользователя {event.organizer.username} уже {active_events_count-1} активных мероприятий. "
                f"Его пакет '{package.name}' позволяет максимум {package.max_active_events} активных мероприятий.",
                level=messages.ERROR
            )
            raise forms.ValidationError(
                f"Превышен лимит активных мероприятий ({package.max_active_events}) для пакета '{package.name}'."
            )
    class Media:
        js = (
            "/static/js/map_admin.js",
            "/static/js/event_admin.js",
        )
        
@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    """
    Настройка отображения типов билетов.
    """

    list_display = (
        "name",
        "event",
        "price",
        "min_quantity",
        "available_quantity",
        "get_sold_count",
        "get_available_count",
        "is_per_person",
    )
    search_fields = ("name", "event__title")
    list_filter = ("is_per_person", "min_quantity")

    def get_sold_count(self, obj):
        """Возвращает количество проданных билетов."""
        return sum(order.quantity for order in obj.orders.exclude(payment_status__in=["refunded", "canceled"]))


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
        return request.user.is_superuser

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
    readonly_fields = ('package', 'start_date', 'end_date', 'is_active', 'subscription_type')
    fields = ('package', 'subscription_type', 'start_date', 'end_date', 'is_active')

    def has_add_permission(self, request, obj=None):
        return True

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser

    def get_formset(self, request, obj=None, **kwargs):
        formset = super().get_formset(request, obj=None, **kwargs)
        formset.extra = 1
        if obj:
            formset.queryset = obj.userpackagesubscription_set.order_by('-start_date')
        return formset


@admin.register(UserPackageSubscription)
class UserPackageSubscriptionAdmin(admin.ModelAdmin):
    """Админка для подписок на пакеты — полный контроль."""

    list_display = ('id', 'user', 'package', 'subscription_type', 'start_date', 'end_date', 'is_active')
    list_filter = ('is_active', 'subscription_type', 'package')
    search_fields = ('user__email', 'user__username', 'package__name')
    readonly_fields = ('start_date',)
    date_hierarchy = 'start_date'

    fieldsets = (
        (None, {
            'fields': ('user', 'package', 'subscription_type')
        }),
        ('Даты', {
            'fields': ('start_date', 'end_date')
        }),
        ('Статус', {
            'fields': ('is_active',)
        }),
    )

    def save_model(self, request, obj, form, change):
        if not change or not obj.start_date:
            obj.start_date = timezone.now()
        super().save_model(request, obj, form, change)

    def response_change(self, request, obj):
        if '_assign_package' in request.POST:
            return self.assign_package_action(request, obj)
        return super().response_change(request, obj)

    def assign_package_action(self, request, obj):
        """Просто редирект — основная логика через action."""
        return redirect(request.META.get('HTTP_REFERER', '/admin/core/userpackagesubscription/'))

    def get_urls(self):
        from django.urls import path

        urls = super().get_urls()
        custom_urls = [
            path(
                'assign_package/',
                self.admin_site.admin_view(self.assign_package_view),
                name='assign_package',
            ),
        ]
        return custom_urls + urls

    def assign_package_view(self, request):
        """Выдать пакет любому партнёру на любой срок."""
        from django.contrib.auth import get_user_model
        from django.shortcuts import render, get_object_or_404
        from django.http import JsonResponse

        users = CustomUser.objects.filter(user_type='partner').order_by('email')
        packages = EventPackage.objects.all()

        if request.method == 'POST':
            user_id = request.POST.get('user_id')
            package_id = request.POST.get('package_id')
            start_date = request.POST.get('start_date')
            end_date = request.POST.get('end_date')

            user = get_object_or_404(CustomUser, id=user_id)
            package = get_object_or_404(EventPackage, id=package_id)

            from django.forms import DateTimeField
            try:
                start = DateTimeField().clean(start_date) if start_date else timezone.now()
            except Exception:
                start = timezone.now()
            try:
                end = DateTimeField().clean(end_date) if end_date else start + timezone.timedelta(days=30)
            except Exception:
                end = start + timezone.timedelta(days=30)

            # Если была активная подписка — деактивируем
            UserPackageSubscription.objects.filter(user=user, is_active=True).update(is_active=False)

            subscription = UserPackageSubscription.objects.create(
                user=user,
                package=package,
                start_date=start,
                end_date=end,
                is_active=True,
                subscription_type='monthly' if package.is_monthly else 'one_time',
            )

            # Если это AJAX — вернём JSON
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({
                    'status': 'ok',
                    'message': f'Пакет "{package.name}" выдан {user.email} до {end_date}',
                })

            self.message_user(
                request,
                f'Пакет "{package.name}" успешно выдан {user.get_full_name()} ({user.email}) до {end.strftime("%d.%m.%Y %H:%M")}',
                messages.SUCCESS,
            )
            return redirect(request.META.get('HTTP_REFERER', '/admin/core/customuser/'))

        return render(request, 'admin/assign_package.html', {
            'users': users,
            'packages': packages,
            'title': 'Выдать пакет партнёру',
        })

    def assign_package(self, request, queryset):
        """Выдать выбранным партнёрам пакет (через модальное окно)."""
        # Просто перенаправляем на форму — основной интерфейс через форму партнёра
        self.message_user(
            request,
            'Используйте кнопку "Выдать пакет" на странице партнёра для выдачи.',
            messages.INFO,
        )

    assign_package.short_description = 'Выдать пакет'

class PartnerPayoutInline(admin.TabularInline):
    model = PayoutRequest
    extra = 0
    readonly_fields = ('amount', 'status', 'created_at', 'payment_details', 'comment')
    fields = ('amount', 'status', 'created_at', 'payment_details', 'comment')

    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser

@admin.register(CustomUser)
class PartnerAdmin(admin.ModelAdmin):
    """
    Кастомная админка для партнёров с полной информацией о подписках, пакетах и активности.
    """

    list_display = (
        'username', 'email', 'get_company_name', 'get_contact_person',
        'get_phone_number', 'has_active_subscription', 'get_active_subscriptions', 'get_total_purchases',
        'verification_status', 'is_verified', 'get_permissions_status'
    )

    list_filter = (
        'user_type',
        'is_verified',
        'verification_status',
    )

    search_fields = (
        'username', 'email', 'partner_profile__company_name', 'partner_profile__contact_person', 'partner_profile__phone'
    )

    inlines = [PartnerSubscriptionInline, PartnerPayoutInline]

    fieldsets = (
        ('Организатор', {
            'fields': ('is_verified', 'verification_status', 'rejection_reason'),
            'description': '1 - Статус организатора (почта), 2 - Статус верификации (дать право партнёру иметь полный функционал), 3 - Причина отказа'
        }),
        ('Аккаунт', {
            'fields': ('user_type', 'first_name', 'last_name', 'username', 'date_joined'),
        }),
        ('Права доступа', {
            'fields': ('can_create_events', 'can_request_reports', 'can_request_payments'),
            'description': 'Функции, доступные партнёру'
        }),
    )

    readonly_fields = ('username', 'email', 'first_name', 'last_name', 'user_type', 'date_joined')

    change_form_template = "admin/partner_change_form.html"
    form = PartnerAdminForm

    def change_view(self, request, object_id, form_url='', extra_context=None):
        extra_context = extra_context or {}
        extra_context['admin_context'] = {
            'users': CustomUser.objects.filter(user_type='partner').order_by('email'),
            'packages': EventPackage.objects.all(),
        }
        return super().change_view(request, object_id, form_url, extra_context=extra_context)

    def get_company_name(self, obj):
        if hasattr(obj, 'partner_profile') and obj.partner_profile:
            return obj.partner_profile.company_name or '-'
        return '-'
    get_company_name.short_description = "Компания"

    def get_contact_person(self, obj):
        if hasattr(obj, 'partner_profile') and obj.partner_profile:
            return obj.partner_profile.contact_person or '-'
        return '-'
    get_contact_person.short_description = "Контактное лицо"

    def get_phone_number(self, obj):
        if hasattr(obj, 'partner_profile') and obj.partner_profile:
            return obj.partner_profile.phone or '-'
        return '-'
    get_phone_number.short_description = "Телефон"

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

    def get_permissions_status(self, obj):
        """Показывает статус прав партнёра"""
        if obj.verification_status == 'approved':
            return mark_safe('<span style="color: green; font-weight: bold;">✓ Одобрено</span>')
        elif obj.verification_status == 'rejected':
            return mark_safe('<span style="color: red; font-weight: bold;">✗ Отклонено</span>')
        elif obj.verification_status == 'pending':
            return mark_safe('<span style="color: orange; font-weight: bold;">⏳ На рассмотрении</span>')
        return mark_safe('<span style="color: gray;">—</span>')
    get_permissions_status.short_description = "Статус партнёра"

    def get_is_verified(self, obj):
        """Показывает статус проверенного организатора"""
        if obj.is_verified:
            return mark_safe('<span style="color: green; font-weight: bold;">✓ Да</span>')
        return mark_safe('<span style="color: red; font-weight: bold;">✗ Нет</span>')
    get_is_verified.short_description = "Проверенный организатор"

    def get_queryset(self, request):
        """Фильтруем только партнёров"""
        qs = super().get_queryset(request)
        return qs.filter(user_type='partner').prefetch_related(
            'userpackagesubscription_set',
            'payoutrequest_set',
            'partner_profile'
        )

    def get_inline_instances(self, request, obj=None):
        """Показываем инлайны только для партнёров"""
        if obj and obj.user_type == 'partner':
            return super().get_inline_instances(request, obj)
        return []

    def delete_model(self, request, obj):
        """Удаляем подписки перед удалением пользователя"""
        obj.userpackagesubscription_set.all().delete()
        super().delete_model(request, obj)

    def delete_queryset(self, request, queryset):
        """Удаляем подписки перед массовым удалением пользователей"""
        for obj in queryset:
            obj.userpackagesubscription_set.all().delete()
        super().delete_queryset(request, queryset)

    def save_model(self, request, obj, form, change):
        """Сохраняем модель и обновляем связанные данные"""
        super().save_model(request, obj, form, change)

    def response_change(self, request, obj):
        """Обрабатываем кнопки одобрения/отклонения/выдачи пакета"""
        if '_approve' in request.POST:
            return self.approve_partner(request, obj)
        elif '_reject' in request.POST:
            return self.reject_partner(request, obj)
        elif '_assign_package' in request.POST:
            return self.assign_package_from_form(request, obj)
        return super().response_change(request, obj)
    
    def assign_package_from_form(self, request, obj):
        """Выдаёт пакет из формы партнёра."""
        from django.forms import DateTimeField
        from django.shortcuts import redirect

        user_id = request.POST.get('user_id')
        package_id = request.POST.get('package_id')
        start_date = request.POST.get('start_date')
        end_date = request.POST.get('end_date')

        if not user_id or not package_id:
            self.message_user(request, 'Выберите партнёра и пакет.', messages.ERROR)
            return redirect(request.META.get('HTTP_REFERER', '/admin/core/customuser/'))

        user = get_object_or_404(CustomUser, id=user_id)
        package = get_object_or_404(EventPackage, id=package_id)

        try:
            start = DateTimeField().clean(start_date) if start_date else timezone.now()
        except Exception:
            start = timezone.now()
        try:
            end = DateTimeField().clean(end_date) if end_date else start + timezone.timedelta(days=30)
        except Exception:
            end = start + timezone.timedelta(days=30)

        # Деактивируем текущие активные подписки
        UserPackageSubscription.objects.filter(user=user, is_active=True).update(is_active=False)

        subscription = UserPackageSubscription.objects.create(
            user=user,
            package=package,
            start_date=start,
            end_date=end,
            is_active=True,
            subscription_type='monthly' if package.is_monthly else 'one_time',
        )

        self.message_user(
            request,
            f'Пакет "{package.name}" выдан {user.get_full_name()} ({user.email}) до {end.strftime("%d.%m.%Y %H:%M")}',
            messages.SUCCESS,
        )
        return redirect(request.META.get('HTTP_REFERER', '/admin/core/customuser/'))
    
    def approve_partner(self, request, obj):
        """Одобряет партнёра"""
        obj.verification_status = 'approved'
        obj.is_verified = True
        obj.permissions = obj.permissions or {}  # Сохраняем текущие права
        obj.rejection_reason = None
        obj.save(update_fields=['verification_status', 'is_verified', 'permissions', 'rejection_reason'])
        
        self.message_user(request, f"Партнёр {obj.get_full_name()} успешно одобрен.")
        
        # Отправляем email
        from django.core.mail import send_mail
        from django.conf import settings
        try:
            send_mail(
                subject='Ваш аккаунт одобрен',
                message=f'''Здравствуйте, {obj.get_full_name()}!

Ваш аккаунт успешно одобрен. Теперь вы можете использовать все функции платформы.

С уважением,
Администрация платформы''',
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[obj.email],
                fail_silently=False,
            )
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Не удалось отправить email об одобрении: {e}")
        
        return redirect(request.META.get('HTTP_REFERER', '/admin/'))

    def reject_partner(self, request, obj):
        """Отклоняет партнёра с причиной"""
        rejection_reason = request.POST.get('rejection_reason', '')
        obj.verification_status = 'rejected'
        obj.is_verified = False
        obj.permissions = {}  # Сбрасываем права
        obj.rejection_reason = rejection_reason
        obj.save(update_fields=['verification_status', 'is_verified', 'permissions', 'rejection_reason'])
        
        self.message_user(request, f"Партнёр {obj.get_full_name()} отклонён.")
        
        # Отправляем email с причиной
        from django.core.mail import send_mail
        from django.conf import settings
        try:
            send_mail(
                subject='Ваш аккаунт отклонён',
                message=f'''Здравствуйте, {obj.get_full_name()}!

Ваш аккаунт был отклонён модератором.

Причина отклонения: {rejection_reason or "Не указана"}

Вы можете исправить данные в настройках профиля и отправить заявку повторно.

С уважением,
Администрация платформы''',
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[obj.email],
                fail_silently=False,
            )
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Не удалось отправить email об отклонении: {e}")
        
        return redirect(request.META.get('HTTP_REFERER', '/admin/'))

# Регистрируем модели, которые ещё не зарегистрированы
try:
    admin.site.unregister(CustomUser)
except:
    pass

# Регистрируем админку для партнёров
admin.site.register(CustomUser, PartnerAdmin)


# Регистрируем подписки на пакеты
@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    """
    Админка для управления категориями мероприятий.
    """
    list_display = ('name',)
    search_fields = ('name',)
    ordering = ('name',)


@admin.register(Format)
class FormatAdmin(admin.ModelAdmin):
    """
    Админка для управления форматами мероприятий.
    """
    list_display = ('name',)
    search_fields = ('name',)
    ordering = ('name',)


