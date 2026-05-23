import os
import django
import json
from django.http import HttpRequest
from django.core.management import call_command

# Настройка окружения Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'activity.settings')
django.setup()

from payment.views import yookassa_webhook
from core.models import Order, Ticket, Event
from django.contrib.auth import get_user_model

User = get_user_model()

def create_test_order():
    # Создаем тестовое мероприятие
    organizer = User.objects.first()
    if not organizer:
        organizer = User.objects.create_user(
            username='test_organizer',
            email='organizer@example.com',
            password='testpass123'
        )

    event = Event.objects.create(
        organizer=organizer,
        title='Тестовое мероприятие',
        description_short='Краткое описание',
        description_full='Полное описание',
        date_time='2026-12-31T23:59:59',
        status='active'
    )

    # Создаем тестовый билет
    ticket = Ticket.objects.create(
        event=event,
        name='Тестовый билет',
        price=100.00,
        available_quantity=100
    )

    # Создаем тестовый заказ
    order = Order.objects.create(
        ticket=ticket,
        participant_data={
            "name": "Дмитрий",
            "email": "dim.anosoff2018@yandex.ru",
            "phone": "+79960521646"
        },
        total_price=100.00,
        quantity=1,
        payment_status="pending"
    )

    return order

def simulate_yookassa_webhook(order):
    # Обновляем заказ, чтобы он имел уникальный yookassa_payment_id
    import uuid
    order.yookassa_payment_id = f"test_payment_id_{uuid.uuid4()}"
    order.save()

    # Имитируем успешную оплату через вебхук ЮКассы
    payment_data = {
        "event": "payment.succeeded",
        "object": {
            "id": order.yookassa_payment_id,
            "status": "succeeded"
        }
    }

    # Создаем фейковый запрос
    class FakeRequest:
        def __init__(self, body):
            self.body = body

        def build_absolute_uri(self, path):
            return f"http://127.0.0.1:8000{path}"

    request = FakeRequest(json.dumps(payment_data))

    # Вызываем вебхук
    response = yookassa_webhook(request)

    return response

if __name__ == "__main__":
    print("Создание тестового заказа...")
    order = create_test_order()
    print(f"Создан заказ с ID: {order.id}")

    print("Имитация успешной оплаты...")
    response = simulate_yookassa_webhook(order)
    print(f"Ответ от вебхука: {response.status_code}")

    print("Проверьте почту dim.anosoff2018@yandex.ru на наличие письма с QR-кодами.")