from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import Event, Ticket, Order, PartnerDocument, PayoutRequest, PayoutDetails
from .models import SupportTicket, SupportMessage, Tag, EventPackage, MainTag, UserPackageSubscription, Category, Format
from .proxy_models import VisitorUser
from .forms import EventAdminForm, PartnerAdminForm
from django import forms
from django.contrib import messages
from django.conf import settings
from django.conf.urls.static import static
from django.utils import timezone
from django.utils.html import mark_safe
from django.db.models import F, Count
from django.contrib.auth import get_user_model
from django.shortcuts import render, redirect, get_object_or_404
from partner_app.models import EventChangeRequest

import logging
logger = logging.getLogger(__name__)

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
            obj.user.organizer_status = "approved"
            obj.user.save(update_fields=['is_verified', 'organizer_status'])
            
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
            obj.user.organizer_status = "rejected"
            obj.user.organizer_rejection_reason = obj.rejection_reason or None
            obj.user.save(update_fields=['organizer_status', 'organizer_rejection_reason'])
            
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
                # Удаляем видеофайл при отклонении (он больше не нужен)
                print(f"[DEBUG] Event {event.id}: video_url={event.video_url}, status={event.status}")
                if event.video_url:
                    video_path = event.video_url.path
                    video_name = event.video_url.name
                    print(f"[DEBUG] УДАЛЯЮ ВИДЕО: path={video_path}, name={video_name}")
                    try:
                        event.video_url.delete(save=False)
                        print(f"[DEBUG] Видео удалено для Event {event.id}")
                    except Exception as e:
                        print(f"[DEBUG] ОШИБКА удаления видео для Event {event.id}: {e}")
                        import traceback
                        traceback.print_exc()
                    event.video_url = None
                    event.video_processing_status = None
                    event.processed_video_url_hash = None
                else:
                    print(f"[DEBUG] video_url пустой для Event {event.id}")

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
        from core.tasks import process_video_task
        for event in queryset:
            self._check_active_events_limit(request, event, is_activating=True)
            # Запускаем обработку видео, если оно есть и статус pending/processing
            if event.video_url and event.video_processing_status in ('pending', 'processing'):
                logger.info(f"to_active: Запуск обработки видео для Event {event.id}")
                process_video_task.delay(
                    model_name='Event',
                    instance_id=event.id,
                    video_field_name='video_url',
                    hash_field_name='processed_video_url_hash',
                    status_field_name='video_processing_status'
                )
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
        form.base_fields['city'].required = False

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
            
            # Удаляем видеофайл при отклонении мероприятия
            if original_status != "rejected" and obj.status == "rejected":
                if obj.video_url:
                    print(f"[DEBUG SAVE_MODEL] Event {obj.id}: удаляю видео {obj.video_url.name}")
                    try:
                        obj.video_url.delete(save=False)
                        print(f"[DEBUG SAVE_MODEL] Видео удалено для Event {obj.id}")
                    except Exception as e:
                        print(f"[DEBUG SAVE_MODEL] ОШИБКА удаления видео для Event {obj.id}: {e}")
                        import traceback
                        traceback.print_exc()
                    obj.video_url = None
                    obj.video_processing_status = None
                    obj.processed_video_url_hash = None

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
        "user_type_label",
        "subject",
        "ticket_type_label",
        "status",
        "event_label",
        "created_at",
    )
    list_filter = ("ticket_type", "status", "created_at")
    readonly_fields = ("user", "subject", "created_at", "event", "ticket_type")
    fieldsets = (
        (None, {"fields": ("user", "user_type_label", "ticket_type", "status")}),
        ("Тикет", {"fields": ("subject", "event_label", "created_at")}),
    )

    def user_type_label(self, obj):
        types = {
            "partner": "🏢 Партнёр",
            "visitor": "👤 Участник",
            "guest": "👤 Гость",
        }
        return types.get(obj.user.user_type, obj.user.user_type)

    user_type_label.short_description = "Тип пользователя"

    def ticket_type_label(self, obj):
        types = {
            "support": "🔧 Техподдержка",
            "participant": "📋 Заявка",
        }
        return types.get(obj.ticket_type, obj.ticket_type)

    ticket_type_label.short_description = "Тип тикета"
    ticket_type_label.admin_order_field = "ticket_type"

    def event_label(self, obj):
        if obj.event:
            return obj.event.title
        return "—"

    event_label.short_description = "Мероприятие"
    event_label.admin_order_field = "event__title"

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.filter(ticket_type='support').select_related("user", "event").prefetch_related("messages")

    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_add_permission(self, request, obj=None):
        return False
@admin.register(PayoutRequest)
class PayoutRequestAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "organizer",
        "amount",
        "balance_at_request",
        "get_status_display",
        "created_at",
    )
    list_filter = ("status", "created_at")
    search_fields = ("id", "payment_details__account_holder", "organizer__email")
    readonly_fields = ("created_at", "balance_at_request")
    actions = ["mark_as_paid", "mark_as_rejected"]

    fieldsets = (
        ("Информация о заявке", {
            "fields": ("organizer", "amount", "status", "created_at", "balance_at_request"),
        }),
        ("Реквизиты", {
            "fields": ("payment_details",),
        }),
        ("Комментарии", {
            "fields": ("comment", "rejection_comment"),
        }),
    )

    def mark_as_paid(self, request, queryset):
        """Action: отметить заявки как выплаченные."""
        updated = queryset.update(status="paid")
        self.message_user(request, f"Отмечено как выплаченные: {updated} заявок.")
    mark_as_paid.short_description = "Отметить как выплаченные"

    def mark_as_rejected(self, request, queryset):
        """Action: отклонить заявки (статус нужно указать в форме)."""
        updated = queryset.update(status="rejected")
        self.message_user(request, f"Отклонено заявок: {updated}. Добавьте комментарий в карточку заявки.")
    mark_as_rejected.short_description = "Отклонить заявки"

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
        ("Описание",
            {
                "fields": (
                    "description",
                    "priority_description",
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
        'get_organizer_status', 'is_verified', 'get_permissions_status'
    )

    list_filter = (
        'user_type',
        'is_verified',
        'verification_status',
        'organizer_status',
    )

    search_fields = (
        'username', 'email', 'partner_profile__company_name', 'partner_profile__contact_person', 'partner_profile__phone'
    )

    inlines = [PartnerSubscriptionInline, PartnerPayoutInline]

    fieldsets = (
        ('Статус партнёра', {
            'fields': ('verification_status', 'rejection_reason'),
            'description': 'Статус заявки партнёра: на рассмотрении (после регистрации), подтверждено/отклонено админом. Причина отказа — если отклонено.'
        }),
        ('Проверенный организатор', {
            'fields': ('is_verified', 'organizer_status', 'organizer_rejection_reason'),
            'description': 'Статус на основе загруженных документов: нет отметки, на рассмотрении, подтверждено, отклонено.'
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

    def get_organizer_status(self, obj):
        """Показывает статус проверенного организатора"""
        if obj.organizer_status == 'approved':
            return mark_safe('<span style="color: green; font-weight: bold;">✓ Подтверждено</span>')
        elif obj.organizer_status == 'rejected':
            return mark_safe('<span style="color: red; font-weight: bold;">✗ Отклонено</span>')
        elif obj.organizer_status == 'pending':
            return mark_safe('<span style="color: orange; font-weight: bold;">⏳ На рассмотрении</span>')
        return mark_safe('<span style="color: gray;">Нет отметки</span>')
    get_organizer_status.short_description = "Проверенный организатор"

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


# === Заявки на изменение мероприятия ===

@admin.register(EventChangeRequest)
class EventChangeRequestAdmin(admin.ModelAdmin):
    """
    Админка заявок на изменение мероприятий.

    Партнёр предлагает изменения к мероприятию с проданными билетами,
    администратор одобряет (изменения применяются) или отклоняет заявку.
    """

    list_display = (
        "id",
        "event",
        "partner",
        "status_badge",
        "changes_summary",
        "created_at",
        "reviewed_at",
    )
    list_filter = ("status", "created_at")
    search_fields = (
        "event__title",
        "partner__email",
        "partner__company_name",
    )
    readonly_fields = (
        "event",
        "partner",
        "status",
        "changes",
        "tickets_data",
        "tag_ids",
        "new_image",
        "new_video_url",
        "new_program_file",
        "clear_image",
        "clear_video_url",
        "clear_program_file",
        "delete_image_ids",
        "primary_image_id",
        "primary_new_image_index",
        "diff_display",
        "tickets_diff_display",
        "created_at",
        "reviewed_at",
        "reviewed_by",
    )
    fieldsets = (
        ("Заявка", {"fields": ("event", "partner", "status", "created_at")}),
        (
            "Предложенные изменения",
            {"fields": ("diff_display", "tickets_diff_display", "new_image", "new_video_url", "new_program_file")},
        ),
        (
            "Решение",
            {"fields": ("admin_comment", "reviewed_by", "reviewed_at")},
        ),
    )
    actions = ("approve_requests", "reject_requests")

    change_form_template = "admin/event_change_request_change_form.html"

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related("event", "partner")
        )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        # Отклонённые и одобренные заявки можно удалять, pending — нет
        if obj and obj.status == "pending":
            return False
        return True

    def get_readonly_fields(self, request, obj=None):
        readonly = list(self.readonly_fields)
        if obj and obj.status != "pending":
            # Рассмотренную заявку больше нельзя менять
            readonly.append("admin_comment")
        return readonly

    # --- Отображение ---

    def status_badge(self, obj):
        colors = {
            "pending": "rgba(255, 131, 72, 1)",
            "approved": "#28a745",
            "rejected": "#dc3545",
        }
        return mark_safe(
            f'<span style="color:#fff; background:{colors.get(obj.status, "#6c757d")};'
            f' padding:2px 10px; border-radius:10px; font-size:12px;">'
            f"{obj.get_status_display()}</span>"
        )
    status_badge.short_description = "Статус"

    def changes_summary(self, obj):
        parts = []
        if obj.changes:
            parts.append(f"полей: {len(obj.changes)}")
        if obj.tickets_data:
            parts.append("билеты")
        if obj.tag_ids:
            parts.append("теги")
        if obj.new_image or obj.clear_image:
            parts.append("фото")
        if obj.new_video_url or obj.clear_video_url:
            parts.append("видео")
        if obj.new_program_file or obj.clear_program_file:
            parts.append("программа")
        if obj.new_gallery_images.exists():
            parts.append(f"новых фото: {obj.new_gallery_images.count()}")
        if obj.delete_image_ids:
            parts.append(f"удалить фото: {len(obj.delete_image_ids)}")
        return ", ".join(parts) or "—"
    changes_summary.short_description = "Состав изменений"

    def diff_display(self, obj):
        """Таблица diff: текущее значение поля vs предложенное."""
        if not obj or not obj.pk:
            return "—"

        rows = obj.get_field_diff_rows()
        has_field_changes = bool(rows)

        html = []
        if has_field_changes:
            html.append(
                '<table style="width:100%; border-collapse:collapse;">'
                '<tr style="background:#f8f9fa;">'
                '<th style="border:1px solid #ddd; padding:6px; text-align:left;">Поле</th>'
                '<th style="border:1px solid #ddd; padding:6px; text-align:left;">Текущее</th>'
                '<th style="border:1px solid #ddd; padding:6px; text-align:left;">Предложено</th>'
                '</tr>'
            )
            for label, current, proposed in rows:
                html.append(
                    f'<tr>'
                    f'<td style="border:1px solid #ddd; padding:6px;">{label}</td>'
                    f'<td style="border:1px solid #ddd; padding:6px; color:#888;">{current}</td>'
                    f'<td style="border:1px solid #ddd; padding:6px; font-weight:bold; color:#b45309;">{proposed}</td>'
                    f'</tr>'
                )
            html.append('</table>')
        else:
            html.append('<p style="color:#888; margin: 4px 0;">Изменений обычных полей нет</p>')

        # Медиафлаги (показываем всегда, даже если нет изменений обычных полей)
        flags = []
        if obj.clear_image:
            flags.append("удалить основное фото")
        if obj.clear_video_url:
            flags.append("удалить видео")
        if obj.clear_program_file:
            flags.append("удалить программу")
        if obj.delete_image_ids:
            flags.append(f"удалить фото галереи: {', '.join(map(str, obj.delete_image_ids))}")
        if obj.tag_ids:
            tag_names = list(obj.event.tags.filter(id__in=obj.tag_ids).values_list("name", flat=True))
            flags.append(f"теги: {', '.join(tag_names) or obj.tag_ids}")
        if flags:
            html.append('<p style="margin-top:8px; color:#b45309;">' + "; ".join(flags) + "</p>")

        # Новые фото галереи
        gallery = obj.new_gallery_images.all()
        if gallery:
            html.append('<p style="margin-top:8px; font-weight:bold;">Новые фото галереи:</p>')
            html.append('<div style="display:flex; flex-wrap:wrap; gap:5px;">')
            for img in gallery:
                primary = " (основное)" if img.is_primary else ""
                html.append(
                    f'<div style="text-align:center;"><img src="{img.image.url}" '
                    f'style="max-width:120px; max-height:120px; border:1px solid #ddd; padding:3px;">'
                    f"<div style='font-size:11px;'>{primary}</div></div>"
                )
            html.append("</div>")

        return mark_safe("".join(html))
    diff_display.short_description = "Изменения полей"

    def tickets_diff_display(self, obj):
        """Сравнение текущих билетов мероприятия с предложенными."""
        if not obj or not obj.pk:
            return "—"
        if not obj.tickets_data:
            return mark_safe('<span style="color:#888;">Изменений билетов нет</span>')

        current = {
            t.name.lower(): t for t in obj.event.tickets.all()
        }
        proposed_names = {row["name"].lower() for row in obj.tickets_data}

        html = [
            '<table style="width:100%; border-collapse:collapse;">',
            '<tr style="background:#f8f9fa;">'
            '<th style="border:1px solid #ddd; padding:6px; text-align:left;">Билет</th>'
            '<th style="border:1px solid #ddd; padding:6px; text-align:left;">Текущий</th>'
            '<th style="border:1px solid #ddd; padding:6px; text-align:left;">Предложено</th>'
            "</tr>",
        ]
        for row in obj.tickets_data:
            ticket = current.get(row["name"].lower())
            if ticket:
                current_str = (
                    f"{ticket.price} руб., мест: {ticket.available_quantity}, "
                    f"продано: {ticket.orders.exclude(payment_status__in=['refunded', 'canceled']).count()}"
                )
                action = "изменение"
            else:
                current_str = "—"
                action = "новый"
            proposed_str = f"{row['price']} руб., мест: {row['quantity']}"
            html.append(
                f"<tr>"
                f'<td style="border:1px solid #ddd; padding:6px;">{row["name"]} <em>({action})</em></td>'
                f'<td style="border:1px solid #ddd; padding:6px; color:#888;">{current_str}</td>'
                f'<td style="border:1px solid #ddd; padding:6px; font-weight:bold; color:#b45309;">{proposed_str}</td>'
                f"</tr>"
            )
        # Билеты, которые партнёр убрал из списка (останутся без изменений)
        removed = [t.name for name, t in current.items() if name not in proposed_names]
        if removed:
            html.append(
                '<tr><td colspan="3" style="border:1px solid #ddd; padding:6px; color:#888;">'
                f"Билеты, отсутствующие в заявке (останутся без изменений): {', '.join(removed)}"
                "</td></tr>"
            )
        html.append("</table>")
        return mark_safe("".join(html))
    tickets_diff_display.short_description = "Изменения билетов"

    # --- Действия ---

    def approve_requests(self, request, queryset):
        """Одобрить выбранные заявки и применить изменения."""
        approved = 0
        for change_request in queryset.filter(status="pending"):
            try:
                change_request.apply_to_event(request.user)
                change_request.notify_partner()
                approved += 1
            except Exception as e:
                logger.error(
                    "Ошибка применения заявки #%s: %s", change_request.pk, e, exc_info=True
                )
                self.message_user(
                    request,
                    f"Не удалось применить заявку #{change_request.pk}: {e}",
                    level=messages.ERROR,
                )
        if approved:
            self.message_user(request, f"Одобрено и применено заявок: {approved}.")
    approve_requests.short_description = "Одобрить и применить изменения"

    def reject_requests(self, request, queryset):
        """Отклонить выбранные заявки (с комментарием)."""
        pending = queryset.filter(status="pending")
        if not pending.exists():
            self.message_user(request, "Нет заявок на рассмотрении.", level=messages.WARNING)
            return None
        if "apply" in request.POST:
            comment = request.POST.get("admin_comment", "")
            for change_request in pending:
                change_request.reject(request.user, comment)
                change_request.notify_partner()
            self.message_user(request, f"Отклонено заявок: {pending.count()}.")
            return None
        # Промежуточная форма ввода комментария
        selected = "".join(
            f'<input type="hidden" name="_selected_action" value="{cr.pk}">'
            for cr in pending
        )
        form = f"""
        <form method="post">
            <input type="hidden" name="action" value="reject_requests">
            <input type="hidden" name="action_check" value="1">
            {selected}
            <div style="margin: 10px 0;">
                <label for="admin_comment">Комментарий партнёру (причина отклонения):</label><br>
                <textarea id="admin_comment" name="admin_comment" rows="4" cols="60"></textarea>
            </div>
            <input type="submit" name="apply" value="Отклонить заявки">
        </form>
        """
        return mark_safe(form)
    reject_requests.short_description = "Отклонить заявки"

    def response_change(self, request, obj):
        """Кнопки 'Одобрить'/'Отклонить' внизу страницы заявки."""
        if "_approve" in request.POST and obj.status == "pending":
            try:
                # Если есть видео — логирование перед обработкой
                if obj.new_video_url:
                    logger.info(f"APPROVE: Заявка #{obj.pk} имеет видео {obj.new_video_url.name}, будет запущена обработка")
                
                obj.apply_to_event(request.user)
                obj.notify_partner()
                
                # Проверка статуса видео после применения
                obj.event.refresh_from_db()
                if obj.event.video_url and obj.event.video_processing_status == 'pending':
                    logger.info(f"APPROVE: Видео для Event {obj.event.id} установлено в статус pending, Celery должен обработать")
                
                self.message_user(request, f"Заявка #{obj.pk} одобрена, изменения применены. Видео будет обработано.")
            except Exception as e:
                logger.error("Ошибка применения заявки #%s: %s", obj.pk, e, exc_info=True)
                self.message_user(request, f"Не удалось применить заявку: {e}", level=messages.ERROR)
            return redirect(request.path)
        if "_reject" in request.POST and obj.status == "pending":
            obj.reject(request.user, request.POST.get("admin_comment_review", ""))
            obj.notify_partner()
            self.message_user(request, f"Заявка #{obj.pk} отклонена.")
            return redirect(request.path)
        return super().response_change(request, obj)


