# core/admin.py

from django.contrib import admin
from .models import Event, Ticket, Order

@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    """
    Настройка отображения модели Event в админке.
    """
    # Какие поля показывать в списке всех мероприятий
    list_display = ('title', 'organizer', 'date_time', 'status', 'commission_rate')
    
    # По каким полям можно фильтровать список
    list_filter = ('status', 'date_time')
    
    # Какие поля использовать для поиска
    search_fields = ('title', 'organizer__username')
    fieldsets = (
        (None, {
            'fields': ('title', 'organizer', 'description_short', 'description_full', 'date_time', 'place')
        }),
        ('Настройки', {
            'fields': ('status', 'image', 'commission_rate', 'auto_close_sales_hours') # Добавь сюда
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
    
    