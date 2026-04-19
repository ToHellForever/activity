"""
Сигналы для приложения core.
"""

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from django.conf import settings
from .models import Order
from .tasks import check_unpaid_bookings
from django.utils import timezone
from django_celery_beat.models import PeriodicTask, IntervalSchedule

User = get_user_model()

@receiver(post_save, sender=Order)
def handle_unpaid_booking(sender, instance, created, **kwargs):
    """
    Обработчик для создания задачи проверки просроченных бронирований.
    """
    if created and not instance.is_paid and instance.payment_deadline:
        # Проверяем, существует ли уже задача
        schedule, created = IntervalSchedule.objects.get_or_create(
            every=1,
            period=IntervalSchedule.HOURS,
        )
        
        # Создаем или обновляем периодическую задачу
        PeriodicTask.objects.get_or_create(
            name='check_unpaid_bookings',
            interval=schedule,
            task='core.tasks.check_unpaid_bookings',
            defaults={
                'enabled': True,
            }
        )

@receiver(post_save, sender=User)
def set_default_user_type(sender, instance, created, **kwargs):
    """
    После создания пользователя автоматически назначаем тип:
    - Если пользователь admin (is_staff=True), устанавливаем тип 'guest'.
    - Если пользователь не admin, устанавливаем тип 'visitor'.
    """
    if created:
        if instance.is_staff:
            # Админы изначально будут с типом "Гость"
            if instance.user_type not in ["visitor", "partner"]:
                instance.user_type = "visitor"
                instance.save()
        else:
            # Обычные пользователи получают тип "Посетитель"
            if instance.user_type == "visitor":
                instance.user_type = "guest"
                instance.save()