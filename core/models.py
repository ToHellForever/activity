from django.contrib.auth.models import AbstractUser
from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator


class CustomUser(AbstractUser):
    """Модель для пользователя."""
    USER_TYPE_CHOICES = (
        ('visitor', 'Посетитель'),
        ('partner', 'Партнёр'),
    )
    user_type = models.CharField(max_length=10, choices=USER_TYPE_CHOICES, default='visitor')
    
    class Meta:
        verbose_name = 'Пользователь'
        verbose_name_plural = 'Пользователи'
    
User = get_user_model()

class Event(models.Model):
    """Модель для мероприятия."""
    STATUS_CHOICES = [
        ('draft', 'Черновик'),
        ('on_moderation', 'На модерации'),
        ('active', 'Активно'),
        ('completed', 'Завершено'),
        ('archived', 'Архив'),
    ]

    organizer = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='Организатор')
    title = models.CharField(max_length=255, verbose_name='Название')
    description_short = models.TextField(verbose_name='Краткое описание')
    description_full = models.TextField(verbose_name='Полное описание')
    date_time = models.DateTimeField(verbose_name='Дата и время')
    place = models.CharField(max_length=255, verbose_name='Место проведения')
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='draft',
        verbose_name='Статус'
    )
    image = models.ImageField(upload_to='event_images/', blank=True, null=True, verbose_name='Изображение')
    
    # Автоматическое закрытие продаж (в часах)
    auto_close_sales_hours = models.PositiveIntegerField(
        default=0, 
        verbose_name='Закрыть продажи за (часов)',
        help_text='0 - не закрывать автоматически'
    )
    commission_rate = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=10.00, # Ставим дефолтное значение
        verbose_name='Комиссия (%)'
    )
    def __str__(self):
        return self.title

    class Meta:
        verbose_name = 'Мероприятие'
        verbose_name_plural = 'Мероприятия'
        ordering = ['-date_time']
        
class Ticket(models.Model):
    """Модель для типа билета (VIP, Стандарт)."""
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='tickets', verbose_name='Мероприятие')
    name = models.CharField(max_length=50, verbose_name='Название билета')
    price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='Цена')
    available_quantity = models.PositiveIntegerField(verbose_name='Количество мест')
    
    def __str__(self):
        return f"{self.name} ({self.event.title})"

    class Meta:
        verbose_name = 'Билет'
        verbose_name_plural = 'Билеты'

class Order(models.Model):
    """Модель для заказа (покупки)."""
    participant_data = models.JSONField(verbose_name='Данные участника') # Хранит имя, email и т.д.
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name='orders', verbose_name='Билет')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')
    total_price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='Общая стоимость')

    def __str__(self):
        return f"Заказ #{self.id} - {self.ticket.name}"
    
    class Meta:
        verbose_name = 'Заказ'
        verbose_name_plural = 'Заказы'
        
        

class PayoutRequest(models.Model):
    """Модель для запроса выплаты партнером."""
    STATUS_CHOICES = [
        ('pending', 'Ожидает'),
        ('processing', 'В обработке'),
        ('paid', 'Выплачено'),
        ('rejected', 'Отклонено'),
    ]

    organizer = models.ForeignKey(User, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='Сумма к выплате')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    payout_method = models.JSONField(verbose_name='Реквизиты для выплаты') # Хранит номер счета, ИНН и т.д.
    
    def __str__(self):
        return f"Запрос #{self.id} - {self.get_status_display()}"
    
    class Meta:
        verbose_name = 'Запрос на выплату'
        verbose_name_plural = 'Запросы на выплату'