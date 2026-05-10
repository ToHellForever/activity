# -*- coding: utf-8 -*-
"""
Тест для проверки гонок (race condition) в системе покупки билетов.
Использует Django Test Client для имитации конкурентных запросов.
"""

import threading
import time
from django.test import Client
from django.contrib.auth import get_user_model
from core.models import Event, Ticket, Order
from django.utils import timezone


def setup_test_data():
    """Создает тестовые данные: пользователя, мероприятие и билет."""
    User = get_user_model()

    # Создаем пользователя-организатора
    organizer, _ = User.objects.get_or_create(
        username="testorganizer",
        defaults={
            "email": "organizer@example.com",
            "first_name": "Test",
            "last_name": "Organizer",
            "user_type": "partner",
        },
    )
    if not organizer.pk:
        organizer.set_password("testpass123")
        organizer.save()

    # Создаем мероприятие
    event, _ = Event.objects.get_or_create(
        id=999,  # Используем уникальный ID для теста
        defaults={
            "title": "Test Event for Race Condition",
            "organizer": organizer,
            "date_time": timezone.now() + timezone.timedelta(days=7),
            "status": "active",
            "auto_close_sales_hours": 0,
            "allow_booking_without_payment": False,
            "description_short": "Test description",
            "description_full": "Test description full",
        },
    )

    # Создаем билет с количеством 1
    ticket, _ = Ticket.objects.get_or_create(
        id=999,  # Используем уникальный ID для теста
        event=event,
        defaults={
            "name": "Race Condition Test Ticket",
            "price": 100.00,
            "available_quantity": 1,  # Только 1 билет для проверки гонок
        },
    )

    return ticket


def buy_ticket(client, user_id, ticket_id):
    """Имитирует покупку билета пользователем."""
    # Получаем страницу покупки для установки CSRF токена
    response = client.get(f"/buy-ticket/{ticket_id}/")

    # Данные для покупки
    data = {
        "email": f"user{user_id}@example.com",
        "first_name": f"User{user_id}",
        "last_name": f"Test{user_id}",
        "phone": "1234567890",
        f"quantity_{ticket_id}": 1,
        "csrfmiddlewaretoken": response.cookies["csrftoken"].value,
    }

    # Отправляем запрос на покупку
    response = client.post(f"/buy-ticket/{ticket_id}/", data=data)
    return response.status_code


def run_race_condition_test():
    """Запускает тест на гонки."""
    # Создаем тестовые данные
    ticket = setup_test_data()
    print(
        f"Создан тестовый билет ID:{ticket.id} с количеством: {ticket.available_quantity}"
    )

    # Проверяем начальное количество билетов
    initial_quantity = ticket.get_available_count()
    print(f"Начальное доступное количество: {initial_quantity}")

    # Создаем двух клиентов
    client1 = Client()
    client2 = Client()

    # Результаты покупок
    results = {"user1": None, "user2": None}

    def test_user(user_id):
        """Функция для запуска в потоке."""
        results[f"user{user_id}"] = buy_ticket(
            client1 if user_id == 1 else client2, user_id, ticket.id
        )

    # Запускаем потоки для имитации одновременной покупки
    thread1 = threading.Thread(target=test_user, args=(1,))
    thread2 = threading.Thread(target=test_user, args=(2,))

    thread1.start()
    thread2.start()

    thread1.join()
    thread2.join()

    # Проверяем итоговое количество билетов
    ticket.refresh_from_db()
    final_quantity = ticket.get_available_count()
    orders_count = Order.objects.filter(ticket_id=ticket.id).count()

    print(f"Итоговое доступное количество: {final_quantity}")
    print(f"Всего создано заказов: {orders_count}")
    print(
        f"Статусы ответов: Пользователь 1 - {results['user1']}, Пользователь 2 - {results['user2']}"
    )

    # Анализ результатов
    if initial_quantity - final_quantity > 1:
        print("❌ ОБНАРУЖЕНА ГОНКА: Продано больше билетов, чем доступно!")
        return True  # Гонка обнаружена
    else:
        print("✅ Гонок не обнаружено")
        return False  # Гонок нет


def fix_race_condition():
    """Исправляет проблему гонок в модели Ticket."""
    from django.db import transaction
    from core.models import Ticket

    # Модифицируем метод is_available для использования блокировки
    original_is_available = Ticket.is_available

    def is_available_with_lock(self, quantity=1):
        """Проверяет доступность билетов с блокировкой."""
        try:
            with transaction.atomic():
                # Блокируем строку билета для предотвращения гонок
                ticket = Ticket.objects.select_for_update().get(pk=self.pk)
                sold = sum(order.quantity for order in ticket.orders.all())
                available = ticket.available_quantity - sold
                return available >= quantity
        except Ticket.DoesNotExist:
            return False

    # Заменяем оригинальный метод
    Ticket.is_available = is_available_with_lock

    # Также модифицируем метод get_available_count для согласованности
    original_get_available_count = Ticket.get_available_count

    def get_available_count_with_lock(self):
        """Возвращает доступное количество билетов с блокировкой."""
        try:
            with transaction.atomic():
                ticket = Ticket.objects.select_for_update().get(pk=self.pk)
                sold = sum(order.quantity for order in ticket.orders.all())
                return ticket.available_quantity - sold
        except Ticket.DoesNotExist:
            return 0

    Ticket.get_available_count = get_available_count_with_lock

    print(
        "✅ Методы Ticket.is_available и Ticket.get_available_count модифицированы для защиты от гонок"
    )


if __name__ == "__main__":
    import os
    import django

    # Настраиваем Django-окружение
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "activity.settings")
    django.setup()

    print("=== Запуск теста на гонки ===")

    # Проверяем наличие гонок
    race_detected = run_race_condition_test()

    if race_detected:
        print("\n=== Исправление проблемы ===")
        fix_race_condition()
        print("\n=== Повторный тест после исправления ===")
        run_race_condition_test()
