# -*- coding: utf-8 -*-
"""
Скрипт для тестирования race condition при одновременной покупке билетов.

Имитирует N пользователей, пытающихся купить последние билеты одновременно.
Проверяет, что продано ровно столько билетов, сколько есть в наличии.

Использование:
    python test_race_condition.py

Настройки в начале файла.
"""

import os
import sys
import json
import time
import uuid
import threading
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

# ============================================================
# НАСТРОЙКИ
# ============================================================

# URL вашего Django-сервера
BASE_URL = "http://127.0.0.1:8000"

# Количество одновременных "пользователей" (запросов)
NUM_USERS = 10

# Количество билетов на мероприятие (должно быть меньше NUM_USERS для наглядности)
TICKET_AVAILABLE = 1

# Цена билета (0 = бесплатный)
TICKET_PRICE = 100

# Тип теста: 'single' или 'bulk'
TEST_TYPE = "single"  # 'single' = один билет за раз, 'bulk' = несколько типов

# Email-префикс для уникализации запросов
EMAIL_PREFIX = f"test_race_{uuid.uuid4().hex[:8]}"


def get_csrf_token(session, event_id):
    """Получает CSRF токен от сервера (не нужен, так как отключили middleware)."""
    return None

# ============================================================
# ИНИЦИАЛИЗАЦИЯ DJANGO
# ============================================================

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "activity.settings")
import django
django.setup()

# Отключаем CSRF проверку для тестового скрипта
from django.conf import settings
if 'django.middleware.csrf.CsrfViewMiddleware' in settings.MIDDLEWARE:
    settings.MIDDLEWARE = [m for m in settings.MIDDLEWARE if m != 'django.middleware.csrf.CsrfViewMiddleware']

from core.models import Event, Ticket, Order
from core.models import CustomUser
from django.utils import timezone
from datetime import timedelta


def setup_test_event():
    """
    Создаёт тестовое мероприятие с одним типом билета.
    Возвращает event и ticket объекты.
    """
    print("\n" + "=" * 60)
    print("STEP 1: Создание тестового мероприятия")
    print("=" * 60)
    
    # Создаём тестового пользователя, если нет
    test_user = CustomUser.objects.filter(username="test_organizer").first()
    if not test_user:
        test_user = CustomUser.objects.create_user(
            username="test_organizer",
            email="test_organizer@test.com",
            password="testpass123",
            user_type="partner"
        )
        print(f"  [OK] Создан тестовый пользователь: {test_user.username} (ID: {test_user.id})")
    else:
        print(f"  [*] Найден тестовый пользователь: {test_user.username} (ID: {test_user.id})")
    
    # Удаляем старые тестовые данные, если есть
    old_ticket = Ticket.objects.filter(name="Тестовый билет Race Condition").first()
    if old_ticket:
        print(f"  [X] Удаляем старый тестовый билет (ID: {old_ticket.id})")
        old_ticket.event.delete()
    
    # Создаём мероприятие
    event = Event.objects.create(
        organizer=test_user,
        title=f"Тест Race Condition {uuid.uuid4().hex[:8]}",
        description="Тестовое мероприятие для проверки race condition",
        date_time=timezone.now() + timedelta(days=1),
        status="active",
        allow_booking_without_payment=False,
    )
    print(f"  [OK] Создано мероприятие: {event.title} (ID: {event.id})")
    
    # Создаём тип билета
    ticket = Ticket.objects.create(
        event=event,
        name="Тестовый билет Race Condition",
        price=TICKET_PRICE,
        available_quantity=TICKET_AVAILABLE,
        ticket_description="Тестовый билет для проверки",
    )
    print(f"  [OK] Создан тип билета: {ticket.name}")
    print(f"       Цена: {ticket.price} rub")
    print(f"       Доступно: {ticket.available_quantity} шт")
    
    return event, ticket


def cleanup_test_data(event):
    """Удаляет тестовое мероприятие и связанные данные."""
    print("\n" + "=" * 60)
    print("STEP 3: Очистка тестовых данных")
    print("=" * 60)
    
    ticket = Ticket.objects.filter(event=event).first()
    if ticket:
        ticket.delete()
    
    event.delete()
    print(f"  [OK] Тестовое мероприятие удалено")

    # Удаляем тестового пользователя
    test_user = CustomUser.objects.filter(username="test_organizer").first()
    if test_user:
        test_user.delete()
        print(f"  [OK] Тестовый пользователь удалён")


def get_available_tickets(ticket):
    """Получает текущее количество доступных билетов."""
    sold = sum(
        order.quantity
        for order in ticket.orders.exclude(
            payment_status__in=["refunded", "canceled"]
        )
    )
    return max(0, ticket.available_quantity - sold)


def simulate_purchase(user_id, event_id, ticket_id, session):
    """
    Имитирует покупку билета одним пользователем.
    """
    url = f"{BASE_URL}/payment/bulk-buy/{event_id}/"
    
    data = {
        "tickets": [
            {
                "id": ticket_id,
                "quantity": 1
            }
        ],
        "total_price": TICKET_PRICE,
        "name": f"Тестовый пользователь {user_id}",
        "email": f"{EMAIL_PREFIX}_user{user_id}@test.com",
        "phone": f"+7900000000{user_id:04d}",
    }
    
    try:
        start_time = time.time()
        headers = {
            "Content-Type": "application/json",
        }
        response = session.post(
            url,
            json=data,
            headers=headers,
            timeout=30
        )
        elapsed = time.time() - start_time
        
        result = {
            "user_id": user_id,
            "status_code": response.status_code,
            "response": response.json() if response.status_code != 200 else response.json(),
            "elapsed": round(elapsed, 3),
            "success": response.status_code == 200 and response.json().get("success", False),
        }
        
        return result
    
    except requests.exceptions.ConnectionError:
        return {
            "user_id": user_id,
            "status_code": 0,
            "response": {"error": "Сервер не доступен"},
            "elapsed": 0,
            "success": False,
        }
    except Exception as e:
        return {
            "user_id": user_id,
            "status_code": 0,
            "response": {"error": str(e)},
            "elapsed": 0,
            "success": False,
        }


def run_race_test():
    """
    Запускает тест race condition.
    """
    print("\n" + "=" * 60)
    print("STEP 2: Запуск теста race condition")
    print("=" * 60)
    print(f"  Количество пользователей: {NUM_USERS}")
    print(f"  Билетов в наличии: {TICKET_AVAILABLE}")
    print(f"  Тип теста: {TEST_TYPE}")
    print()
    
    # Получаем текущие данные
    ticket = Ticket.objects.filter(name="Тестовый билет Race Condition").first()
    event = ticket.event if ticket else None
    
    if not ticket or not event:
        print("  [ERROR] Тестовые данные не найдены!")
        return
    
    print(f"  Перед тестом:")
    print(f"    - Available quantity: {ticket.available_quantity}")
    sold = sum(
        order.quantity
        for order in ticket.orders.exclude(
            payment_status__in=["refunded", "canceled"]
        )
    )
    print(f"    - Продано: {sold}")
    print(f"    - Осталось: {get_available_tickets(ticket)}")
    
    # Сбрасываем заказы на этом билете
    Order.objects.filter(ticket=ticket).delete()
    ticket.refresh_from_db()
    print(f"\n  [OK] Заказы сброшены")
    
    # Создаём сессию
    session = requests.Session()
    print(f"  [*] Сессия создана (CSRF отключен)")
    
    # Запускаем одновременные запросы
    print(f"\n  Запускаем {NUM_USERS} одновременных запросов...")
    print("  " + "-" * 50)
    
    results = []
    start_time = time.time()
    
    with ThreadPoolExecutor(max_workers=NUM_USERS) as executor:
        futures = {
            executor.submit(simulate_purchase, uid, event.id, ticket.id, session): uid
            for uid in range(1, NUM_USERS + 1)
        }
        
        for future in as_completed(futures):
            uid = futures[future]
            try:
                result = future.result()
                results.append(result)
                
                status_icon = "[OK]" if result["success"] else "[FAIL]"
                status_text = "УСПЕХ" if result["success"] else f"ОШИБКА ({result['status_code']})"
                print(f"  {status_icon} Пользователь {uid}: {status_text} ({result['elapsed']}s)")
                
            except Exception as e:
                print(f"  [FAIL] Пользователь {uid}: Исключение - {e}")
    
    total_time = time.time() - start_time
    
    # Анализируем результаты
    print("\n  " + "-" * 50)
    print("  РЕЗУЛЬТАТЫ ТЕСТА:")
    print("  " + "-" * 50)
    
    successful = [r for r in results if r["success"]]
    failed = [r for r in results if not r["success"]]
    
    print(f"  Всего запросов:    {len(results)}")
    print(f"  Успешных:          {len(successful)}")
    print(f"  Неудачных:         {len(failed)}")
    print(f"  Общее время:       {total_time:.3f}s")
    
    # Проверяем, что продано ровно TICKET_AVAILABLE билетов
    ticket.refresh_from_db()
    sold_after = sum(
        order.quantity
        for order in ticket.orders.exclude(
            payment_status__in=["refunded", "canceled"]
        )
    )
    available_after = get_available_tickets(ticket)
    
    print(f"\n  Состояние после теста:")
    print(f"    - Available quantity (БД): {ticket.available_quantity}")
    print(f"    - Продано (из заказов):    {sold_after}")
    print(f"    - Осталось (расчёт):       {available_after}")
    
    # Финальная оценка
    print("\n" + "=" * 60)
    if sold_after == TICKET_AVAILABLE and available_after == 0:
        print("  [PASS] ТЕСТ ПРОЙДЕН!")
        print("  Race condition отсутствует.")
        print("  Продано ровно столько билетов, сколько было доступно.")
    elif sold_after > TICKET_AVAILABLE:
        print("  [FAIL] ТЕСТ ПРОВАЛЕН!")
        print("  RACE CONDITION ОБНАРУЖЕНА!")
        print(f"  Продано {sold_after} билетов, но доступно было только {TICKET_AVAILABLE}.")
        print("  Перепродажа:", sold_after - TICKET_AVAILABLE, "билетов!")
    else:
        print("  [WARN] ТЕСТ НЕОПРЕДЕЛЁННЫЙ")
        print(f"  Продано {sold_after} из {TICKET_AVAILABLE} доступных.")
        print("  Возможно, сервер не обрабатывал запросы.")
    print("=" * 60)
    
    return {
        "total": len(results),
        "successful": len(successful),
        "failed": len(failed),
        "sold_after": sold_after,
        "available_after": available_after,
        "test_passed": sold_after == TICKET_AVAILABLE and available_after == 0,
    }


def main():
    """Основная функция."""
    print("\n" + "#" * 60)
    print("# ТЕСТ RACE CONDITION - ПОКУПКА БИЛЕТОВ")
    print("#" * 60)
    
    try:
        # Шаг 1: Создание тестовых данных
        event, ticket = setup_test_event()
        
        # Шаг 2: Запуск теста
        results = run_race_test()
        
        # Шаг 3: Очистка
        cleanup_test_data(event)
        
        # Вывод итога
        print("\n" + "#" * 60)
        print("# ИТОГ ТЕСТА")
        print("#" * 60)
        if results and results.get("test_passed"):
            print("[OK] Защита от race condition РАБОТАЕТ корректно.")
        else:
            print("[FAIL] Защита от race condition НЕ РАБОТАЕТ!")
            print("  Обнаружена перепродажа билетов!")
    except KeyboardInterrupt:
        print("\n\n  Тест прерван пользователем.")
        sys.exit(1)
    except Exception as e:
        print(f"\n  [ERROR] КРИТИЧЕСКАЯ ОШИБКА: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
