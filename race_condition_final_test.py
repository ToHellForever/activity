# -*- coding: utf-8 -*-
"""
Финальный тест для проверки исправленной системы покупки билетов.
Включает тестирование с Redis (если доступен) и без него.
"""

import threading
import time
from django.test import Client
from django.contrib.auth import get_user_model
from core.models import Event, Ticket, Order
from django.utils import timezone
import logging

# Настройка логирования
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger(__name__)


def setup_test_data():
    """Создает тестовые данные для финального теста."""
    User = get_user_model()

    # Создаем пользователя-организатора
    organizer, _ = User.objects.get_or_create(
        username="final_test_organizer",
        defaults={
            "email": "final_organizer@example.com",
            "first_name": "Final",
            "last_name": "Test Organizer",
            "user_type": "partner",
        },
    )
    if not organizer.pk:
        organizer.set_password("testpass123")
        organizer.save()

    # Создаем мероприятие
    event, _ = Event.objects.get_or_create(
        id=2001,
        defaults={
            "title": "Final Race Condition Test Event",
            "organizer": organizer,
            "date_time": timezone.now() + timezone.timedelta(days=7),
            "status": "active",
            "auto_close_sales_hours": 0,
            "allow_booking_without_payment": False,
            "description_short": "Final test for race condition",
            "description_full": "Final comprehensive test",
        },
    )

    # Создаем билет с количеством 1
    ticket, _ = Ticket.objects.get_or_create(
        id=2001,
        event=event,
        defaults={
            "name": "Final Test Ticket",
            "price": 100.00,
            "available_quantity": 1,  # Только 1 билет для проверки
        },
    )

    return ticket


def buy_ticket(client, user_id, ticket_id):
    """Имитирует покупку билета с полным циклом."""
    logger.debug(f"User {user_id}: Starting purchase process")

    try:
        # Получаем страницу покупки для установки CSRF токена
        response = client.get(f"/buy-ticket/{ticket_id}/")
        if response.status_code != 200:
            logger.error(
                f"User {user_id}: Failed to get ticket page. Status: {response.status_code}"
            )
            return response.status_code

        csrftoken = response.cookies.get("csrftoken")
        if not csrftoken:
            logger.error(f"User {user_id}: CSRF token not found")
            return 403

        # Данные для покупки
        data = {
            "email": f"user{user_id}@example.com",
            "first_name": f"User{user_id}",
            "last_name": f"Test{user_id}",
            "phone": "1234567890",
            f"quantity_{ticket_id}": 1,
            "csrfmiddlewaretoken": csrftoken,
        }

        logger.debug(f"User {user_id}: Sending purchase request")
        response = client.post(f"/buy-ticket/{ticket_id}/", data=data)

        logger.debug(f"User {user_id}: Received response status {response.status_code}")
        return response.status_code

    except Exception as e:
        logger.error(f"User {user_id}: Error during purchase - {str(e)}")
        return 500


def test_with_redis(use_redis=True):
    """Тестирует систему с использованием Redis (если доступен)."""
    try:
        from core.redis_utils import get_redis_connection

        redis_conn = get_redis_connection()

        if use_redis and redis_conn:
            logger.info("Testing with Redis distributed locking")
            # Redis уже настроен в модели через REDIS_AVAILABLE
            return True
        else:
            logger.info("Testing with local database locking")
            return False
    except ImportError:
        logger.info("Redis not available. Using local locking only.")
        return False


def run_final_test():
    """Запускает финальный тест с полным покрытием."""
    logger.info("=== Starting Final Race Condition Test ===")

    # Проверяем доступность Redis
    redis_available = test_with_redis()
    logger.info(f"Redis available: {redis_available}")

    # Создаем тестовые данные
    ticket = setup_test_data()
    logger.info(
        f"Created test ticket ID:{ticket.id} with quantity: {ticket.available_quantity}"
    )

    # Проверяем начальное количество билетов
    initial_quantity = ticket.get_available_count()
    logger.info(f"Initial available quantity: {initial_quantity}")

    # Создаем клиентов
    clients = [Client() for _ in range(5)]  # Тестируем с 5 пользователями

    # Результаты покупок
    results = {f"user{i+1}": None for i in range(5)}

    def test_user(user_id):
        """Функция для запуска в потоке."""
        results[f"user{user_id}"] = buy_ticket(clients[user_id - 1], user_id, ticket.id)

    # Запускаем потоки для имитации одновременной покупки
    threads = []
    for i in range(1, 6):
        thread = threading.Thread(target=test_user, args=(i,))
        threads.append(thread)
        thread.start()
        time.sleep(0.05)  # Небольшая задержка

    # Ждем завершения всех потоков
    for thread in threads:
        thread.join()

    # Обновляем данные о билете
    ticket.refresh_from_db()
    final_quantity = ticket.get_available_count()
    orders_count = Order.objects.filter(ticket_id=ticket.id).count()

    logger.info(f"Final available quantity: {final_quantity}")
    logger.info(f"Total orders created: {orders_count}")

    # Выводим статусы ответов
    for user_id, status in results.items():
        logger.info(f"{user_id}: {status}")

    # Анализ результатов
    successful_purchases = sum(1 for status in results.values() if status in [200, 302])

    if successful_purchases > initial_quantity:
        logger.error(
            f"❌ FAIL: {successful_purchases} successful purchases for {initial_quantity} available tickets!"
        )
        logger.error("Race condition detected!")
        return False
    else:
        logger.info(
            f"✅ PASS: Only {successful_purchases} successful purchases for {initial_quantity} available tickets"
        )
        logger.info("No race condition detected")
        return True


def run_consistency_check():
    """Запускает проверку согласованности данных."""
    logger.info("\n=== Running Consistency Check ===")

    # Проверяем все билеты
    issues_found = False

    for ticket in Ticket.objects.all():
        # Проверяем через прямые вычисления
        db_sold = sum(order.quantity for order in ticket.orders.all())
        calc_available = ticket.available_quantity - db_sold

        # Проверяем через метод модели
        model_available = ticket.get_available_count()

        if calc_available != model_available:
            logger.error(f"❌ Inconsistency for ticket {ticket.id}:")
            logger.error(f"    Direct calculation: {calc_available}")
            logger.error(f"    Model method: {model_available}")
            issues_found = True

        # Проверяем на отрицательное количество
        if model_available < 0:
            logger.error(
                f"❌ Negative quantity for ticket {ticket.id}: {model_available}"
            )
            issues_found = True

    if not issues_found:
        logger.info("✅ All tickets are consistent")

    return not issues_found


def main():
    """Главная функция для запуска всех тестов."""
    logger.info("=== Final Race Condition Test Suite ===")

    # 1. Тестируем гонки
    race_test_passed = run_final_test()

    # 2. Проверяем согласованность
    consistency_ok = run_consistency_check()

    # 3. Итоговый отчет
    logger.info("\n=== Final Results ===")

    if race_test_passed and consistency_ok:
        logger.info("🎉 ALL TESTS PASSED: System is protected from race conditions!")
        logger.info("✅ No race conditions detected")
        logger.info("✅ All data is consistent")
    else:
        logger.error("❌ TESTS FAILED: Issues detected!")
        if not race_test_passed:
            logger.error("  - Race condition detected in purchase test")
        if not consistency_ok:
            logger.error("  - Data consistency issues found")

    logger.info("\n=== Recommendations ===")
    logger.info(
        "1. For single-server deployments: Current implementation is sufficient"
    )
    logger.info(
        "2. For distributed systems: Enable Redis by installing 'redis' package"
    )
    logger.info(
        "3. Regularly run consistency checks with: python manage.py check_race_conditions"
    )
    logger.info("4. Monitor system logs for any race condition warnings")


if __name__ == "__main__":
    import os
    import django

    # Настраиваем Django-окружение
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "activity.settings")
    django.setup()

    main()
