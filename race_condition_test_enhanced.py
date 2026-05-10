# -*- coding: utf-8 -*-
"""
Расширенный тест для проверки гонок (race condition) в системе покупки билетов.
Включает дополнительные рекомендации и тестирование.
"""

import threading
import time
from django.test import Client
from django.contrib.auth import get_user_model
from core.models import Event, Ticket, Order
from django.utils import timezone
from django.db import transaction, IntegrityError
import logging

# Настройка логирования
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger(__name__)


def setup_test_data():
    """Создает тестовые данные с уникальными ID для избежания конфликтов."""
    User = get_user_model()

    # Создаем пользователя-организатора
    organizer, _ = User.objects.get_or_create(
        username="race_test_organizer",
        defaults={
            "email": "race_organizer@example.com",
            "first_name": "Race",
            "last_name": "Test Organizer",
            "user_type": "partner",
        },
    )
    if not organizer.pk:
        organizer.set_password("testpass123")
        organizer.save()

    # Создаем мероприятие с уникальным ID
    event, _ = Event.objects.get_or_create(
        id=1001,  # Уникальный ID для теста
        defaults={
            "title": "Race Condition Enhanced Test Event",
            "organizer": organizer,
            "date_time": timezone.now() + timezone.timedelta(days=7),
            "status": "active",
            "auto_close_sales_hours": 0,
            "allow_booking_without_payment": False,
            "description_short": "Test for race condition",
            "description_full": "Enhanced test for race condition detection",
        },
    )

    # Создаем билет с количеством 1
    ticket, _ = Ticket.objects.get_or_create(
        id=1001,  # Уникальный ID для теста
        event=event,
        defaults={
            "name": "Race Test Ticket",
            "price": 100.00,
            "available_quantity": 1,  # Только 1 билет для проверки гонок
        },
    )

    return ticket


def enhanced_buy_ticket(client, user_id, ticket_id, use_redis_lock=False):
    """Имитирует покупку билета с дополнительными проверками."""
    logger.debug(f"User {user_id}: Starting ticket purchase process")

    try:
        # Получаем страницу покупки для установки CSRF токена
        response = client.get(f"/buy-ticket/{ticket_id}/")
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


def run_enhanced_race_test():
    """Запускает расширенный тест на гонки с мониторингом."""
    logger.info("=== Starting Enhanced Race Condition Test ===")

    # Создаем тестовые данные
    ticket = setup_test_data()
    logger.info(
        f"Created test ticket ID:{ticket.id} with quantity: {ticket.available_quantity}"
    )

    # Проверяем начальное количество билетов
    initial_quantity = ticket.get_available_count()
    logger.info(f"Initial available quantity: {initial_quantity}")

    # Создаем клиентов
    client1 = Client()
    client2 = Client()
    client3 = Client()  # Добавляем третьего пользователя для более жесткого теста

    # Результаты покупок
    results = {"user1": None, "user2": None, "user3": None}

    def test_user(user_id):
        """Функция для запуска в потоке."""
        results[f"user{user_id}"] = enhanced_buy_ticket(
            client1 if user_id == 1 else client2 if user_id == 2 else client3,
            user_id,
            ticket.id,
        )

    # Запускаем потоки для имитации одновременной покупки
    threads = []
    for i in range(1, 4):  # Тестируем с 3 пользователями
        thread = threading.Thread(target=test_user, args=(i,))
        threads.append(thread)
        thread.start()
        time.sleep(0.1)  # Небольшая задержка для более реалистичной симуляции

    # Ждем завершения всех потоков
    for thread in threads:
        thread.join()

    # Обновляем данные о билете
    ticket.refresh_from_db()
    final_quantity = ticket.get_available_count()
    orders_count = Order.objects.filter(ticket_id=ticket.id).count()

    logger.info(f"Final available quantity: {final_quantity}")
    logger.info(f"Total orders created: {orders_count}")
    logger.info(
        f"Response statuses: User1 - {results['user1']}, User2 - {results['user2']}, User3 - {results['user3']}"
    )

    # Анализ результатов
    successful_purchases = sum(1 for status in results.values() if status in [200, 302])

    if successful_purchases > initial_quantity:
        logger.error(
            f"❌ RACE CONDITION DETECTED: {successful_purchases} successful purchases for {initial_quantity} available tickets!"
        )
        return True  # Гонка обнаружена
    else:
        logger.info("✅ No race condition detected")
        return False  # Гонок нет


def implement_redis_lock():
    """Демонстрация того, как можно реализовать блокировку с Redis."""
    try:
        import redis

        # Подключение к Redis
        r = redis.Redis(host="localhost", port=6379, db=0)

        # Пример использования блокировки
        def locked_purchase(ticket_id, user_id):
            lock = r.lock(f"ticket_{ticket_id}_lock", timeout=10)

            try:
                if lock.acquire(blocking=True, timeout=5):
                    # Критическая секция - проверка и покупка билета
                    logger.info(f"User {user_id}: Acquired lock for ticket {ticket_id}")
                    # Здесь должна быть логика покупки
                    time.sleep(1)  # Имитация обработки
                    logger.info(f"User {user_id}: Released lock for ticket {ticket_id}")
                    return True
                else:
                    logger.warning(
                        f"User {user_id}: Could not acquire lock for ticket {ticket_id}"
                    )
                    return False
            finally:
                if lock.locked():
                    lock.release()

        logger.info("✅ Redis lock implementation example ready")
        return True

    except ImportError:
        logger.warning(
            "Redis library not installed. Use 'pip install redis' for distributed locking."
        )
        return False
    except Exception as e:
        logger.error(f"Redis connection error: {str(e)}")
        return False


def monitor_race_conditions():
    """Пример мониторинга для обнаружения гонок в реальном времени."""
    logger.info("Setting up race condition monitoring...")

    # Пример мониторинга через логи
    def log_suspicious_activity(ticket_id, user_id, action):
        logger.warning(f"Monitoring: User {user_id} {action} for ticket {ticket_id}")

    # Пример мониторинга через базу данных
    def check_inconsistencies():
        from django.db.models import Count

        # Поиск билетов с отрицательным количеством
        problematic_tickets = Ticket.objects.annotate(
            sold=Count("orders__quantity")
        ).filter(available_quantity__lt=0)

        if problematic_tickets.exists():
            logger.error(
                f"Monitoring: Found {problematic_tickets.count()} tickets with negative quantity!"
            )
            return True

        # Поиск билетов, где продано больше, чем доступно
        oversold_tickets = []
        for ticket in Ticket.objects.all():
            sold = sum(order.quantity for order in ticket.orders.all())
            if sold > ticket.available_quantity:
                oversold_tickets.append(ticket)

        if oversold_tickets:
            logger.error(f"Monitoring: Found {len(oversold_tickets)} oversold tickets!")
            return True

        return False

    # Запускаем проверку
    has_issues = check_inconsistencies()
    if has_issues:
        logger.error("❌ Monitoring detected race condition issues!")
    else:
        logger.info("✅ Monitoring: No race condition issues detected")

    return has_issues


def main():
    """Главная функция для запуска всех тестов и рекомендаций."""
    logger.info("=== Starting Enhanced Race Condition Testing ===")

    # 1. Тестируем наличие гонок
    race_detected = run_enhanced_race_test()

    # 2. Проверяем реализацию Redis
    redis_available = implement_redis_lock()

    # 3. Запускаем мониторинг
    monitoring_issues = monitor_race_conditions()

    # 4. Вывод рекомендаций
    logger.info("\n=== Recommendations ===")

    if race_detected:
        logger.error("Race condition detected! Implement the following fixes:")
        logger.info("1. Use select_for_update() in Ticket.is_available() method")
        logger.info("2. Ensure all ticket operations are within transactions")
        logger.info("3. Consider implementing Redis locks for distributed systems")
    else:
        logger.info("No race conditions detected in current test")

    if not redis_available:
        logger.info("Install Redis for distributed locking: pip install redis")

    if monitoring_issues:
        logger.error("Monitoring detected existing race condition issues in database!")
        logger.info("Run consistency checks and fix affected tickets")

    logger.info("\n=== Test Complete ===")


if __name__ == "__main__":
    import os
    import django

    # Настраиваем Django-окружение
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "activity.settings")
    django.setup()

    main()
