"""
Задачи Celery для приложения core.
"""

from celery import shared_task
from django.utils import timezone
from .models import Order
from django.core.mail import send_mail
from django.template.loader import render_to_string


@shared_task
def check_unpaid_bookings():
    """
    Проверяет просроченные бронирования и освобождает места.
    """
    now = timezone.now()
    unpaid_orders = Order.objects.filter(is_paid=False, payment_deadline__lte=now)

    for order in unpaid_orders:
        # Освобождаем места
        ticket = order.ticket
        ticket.available_quantity += order.quantity
        ticket.save()

        # Отправляем уведомление пользователю
        send_booking_cancellation_notification(order)

        # Удаляем заказ
        order.delete()


def send_booking_cancellation_notification(order):
    """
    Отправляет уведомление о отмене бронирования.
    """
    participant_data = order.participant_data
    email = participant_data.get("email")

    if not email:
        return

    subject = "Отмена вашего бронирования"

    message = render_to_string(
        "emails/booking_cancellation.html",
        {
            "order": order,
            "ticket": order.ticket,
            "event": order.ticket.event,
        },
    )

    send_mail(
        subject,
        "",  # Пустое тело, так как используем HTML
        "dim.anosoff2018@yandex.ru",  # Отправитель
        [email],  # Получатель
        html_message=message,
    )
