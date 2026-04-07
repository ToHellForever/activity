from django.contrib import admin
from .models import Event, Ticket, Order
from .models import SupportTicket, SupportMessage
from django import forms
# masseges
from django.contrib import messages


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    """
    Настройка отображения модели Event в админке.
    """
    # Какие поля показывать в списке всех мероприятий
    list_display = ('title', 'organizer', 'date_time', 'status', 'commission_rate')
    
    # По каким полям можно фильтровать список
    list_filter = ('status', 'date_time', 'category') # Можно добавить фильтрацию по категории
    
    # Какие поля использовать для поиска
    search_fields = ('title', 'organizer__username')

    # Группировка полей на странице редактирования
    fieldsets = (
        (None, {
            'fields': ('title', 'organizer', 'description_short', 'description_full', 'date_time', 'place')
        }),
        ('Медиа и Файлы', {
            'fields': ('image', 'video_url', 'program_file')
        }),
        ('Настройки и Категории', {
            'fields': ('status', 'category', 'tags', 'allow_booking_without_payment', 'commission_rate', 'auto_close_sales_hours')
        }),
    )

@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    """
    Настройка отображения типов билетов.
    """
    list_display = ('name', 'event', 'price', 'available_quantity')
    search_fields = ('name', 'event__title')


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    """
    Настройка отображения заказов.
    """
    list_display = ('id', 'ticket', 'created_at', 'total_price')
    list_filter = ('created_at',)

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
    list_display = UserAdmin.list_display + ('user_type',)
    list_filter = UserAdmin.list_filter + ('user_type',)
    
    
class SupportTicketAdminForm(forms.ModelForm):
    moderator_response = forms.CharField(
        widget=forms.Textarea,
        required=False,
        label='Ответ модератора',
        help_text='Ответ будет добавлен в чат и виден пользователю.'
    )
    class Meta:
        model = SupportTicket
        fields = '__all__'

@admin.register(SupportTicket)
class SupportTicketAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'subject', 'status', 'created_at')
    list_filter = ('status', 'created_at')
    readonly_fields = ('user', 'subject', 'created_at')
    form = SupportTicketAdminForm

    # Эта строка уже должна быть здесь
    change_form_template = 'admin/supportticket_change_form.html' 

    fieldsets = (
        (None, {
            'fields': ('user', 'status')
        }),
        ('Тикет', {
            'fields': ('subject', 'created_at')
        }),
        ('Ответ модератора', {
            'fields': ('moderator_response',)
        }),
    )

    # Этот метод тоже должен быть внутри этого единственного класса
    def save_model(self, request, obj, form, change):
        """
        Этот метод вызывается при нажатии кнопки "Сохранить" в админке.
        """
        # 1. СНАЧАЛА сохраняем сам объект (тикет)
        # Это нужно, чтобы у нас был корректный obj.id для связи с сообщением
        obj.save()
        
        # 2. Теперь проверяем, ввел ли модератор ответ
        response_text = form.cleaned_data.get('moderator_response')
        if response_text:
            # 3. Создаем сообщение в чате
            SupportMessage.objects.create(
                ticket=obj,
                user=request.user,
                is_from_user=False,
                text=response_text
            )
            self.message_user(request, "Ответ успешно добавлен в чат.", level=messages.SUCCESS)
            
            # 4. Обновляем объект, чтобы он увидел новые сообщения в чате
            obj.refresh_from_db()
            
            # 5. Меняем статус при необходимости
            if obj.status == 'new':
                obj.status = 'in_progress'
                obj.save() # Сохраняем изменение статуса