"""
Скрипт для выкупа всех билетов на мероприятие 374.

Запуск:
    python manage.py shell buy_all_tickets_374.py

ИЛИ:
    python buy_all_tickets_374.py  (если запускается как standalone)
"""
import os
import sys

# Добавляем проект в path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'activity.settings')

import django
django.setup()

from django.db import transaction, models
from django.db.models import Sum
from core.models import Event, Ticket, Order
from decimal import Decimal


def buy_all_tickets(event_id=374):
    """Выкупает все доступные билеты на указанном мероприятии."""
    print(f"\n{'='*60}")
    print(f"Выкуп всех билетов на мероприятие #{event_id}")
    print(f"{'='*60}\n")

    # 1. Находим мероприятие
    try:
        event = Event.objects.get(id=event_id)
    except Event.DoesNotExist:
        print(f"ERROR: Мероприятие с id={event_id} не найдено!")
        return

    print(f"Мероприятие: {event.title}")
    print(f"Дата: {event.date_time}")
    print(f"Организатор: {event.organizer.email}")
    print()

    # 2. Смотрим все типы билетов
    tickets = Ticket.objects.filter(event=event)
    if not tickets.exists():
        print("ERROR: У мероприятия нет билетов!")
        return

    print("Найденные типы билетов:")
    print(f"{'-'*60}")
    total_slots = 0
    for ticket in tickets:
        sold_aggregated = ticket.orders.exclude(
            payment_status__in=["refunded", "canceled"]
        ).aggregate(total=Sum("quantity"))["total"]
        sold = sold_aggregated or 0
        # available_quantity — живой счётчик: всего = продано + доступно
        total_slots += sold + ticket.available_quantity
        print(
            f"  {ticket.name:<20} "
            f"цена: {ticket.price} руб.  "
            f"всего: {sold + ticket.available_quantity:<5}  "
            f"продано: {sold:<5}  "
            f"доступно: {ticket.available_quantity}"
        )
    print(f"{'-'*60}")
    print(f"Всего мест: {total_slots}")
    print()

    # 3. Подтверждение
    confirm = input(f"Выкупить все {total_slots} билетов? (yes/no): ").strip().lower()
    if confirm != "yes":
        print("Отменено.")
        return

    # 4. Выкупаем (частями, чтобы total_price не превысил лимит Decimal(10,2))
    MAX_TOTAL = Decimal("99999999.99")
    total_orders = 0
    total_tickets = 0
    total_cost = Decimal("0")

    def get_remaining(t):
        """Оставшиеся билеты: available_quantity — живой счётчик."""
        return max(0, t.available_quantity)

    for ticket in tickets:
        ticket = Ticket.objects.get(pk=ticket.pk)  # свежие данные
        remaining = get_remaining(ticket)

        if remaining <= 0:
            print(f"  [SKIP] {ticket.name} — уже все продано")
            continue

        # Максимальная партия, чтобы сумма заказа не превысила лимит поля
        price = ticket.price
        if price <= 0:
            chunk_limit = remaining
        else:
            chunk_limit = int(MAX_TOTAL / price)

        print(f"  [BUY]  {ticket.name} — осталось {remaining} шт. x {price} руб. (партиями до {chunk_limit} шт.)")

        bought_for_ticket = 0
        while True:
            ticket = Ticket.objects.get(pk=ticket.pk)  # перечитываем
            remaining = get_remaining(ticket)
            if remaining <= 0:
                break

            quantity = min(remaining, chunk_limit)
            if quantity <= 0:
                break

            try:
                with transaction.atomic():
                    t_locked = Ticket.objects.select_for_update().get(pk=ticket.pk)

                    order = Order.objects.create(
                        ticket=t_locked,
                        quantity=quantity,
                        participant_data={
                            "first_name": "Тестовый покупатель",
                            "last_name": "",
                            "email": "test+bots@example.com",
                            "phone": "",
                        },
                        total_price=t_locked.price * quantity,
                        payment_status="succeeded",
                        is_paid=True,
                        purchase_type="paid_ticket",
                        platform_commission=Decimal("0"),
                    )

                    # Атомарно декрементируем available_quantity (как в reserve_tickets)
                    updated = Ticket.objects.filter(
                        pk=t_locked.pk,
                        available_quantity__gte=quantity
                    ).update(
                        available_quantity=models.F("available_quantity") - quantity
                    )

                    if updated == 0:
                        order.delete()
                        print(f"    ERROR: не удалось декрементировать available_quantity")
                        break

                total_orders += 1
                total_tickets += quantity
                total_cost += order.total_price
                bought_for_ticket += quantity
                print(f"    OK — заказ #{order.id}: {quantity} шт. на {order.total_price} руб.")
            except Exception as e:
                print(f"    ERROR: {e}")
                break

        print(f"    Итого по '{ticket.name}': выкуплено {bought_for_ticket} шт.")

    print(f"\n{'='*60}")
    print(f"Итого:")
    print(f"  Заказов: {total_orders}")
    print(f"  Билетов: {total_tickets}")
    print(f"  Сумма:   {total_cost} руб.")
    print(f"{'='*60}\n")

    # 5. Проверяем распроданность и шлём уведомление (как это делает сайт)
    event = Event.objects.get(id=event_id)
    print(f"Все билеты проданы: {event.has_all_tickets_sold}")
    if event.has_all_tickets_sold:
        try:
            from partner_app.views.events import send_partner_all_tickets_sold_notification
            send_partner_all_tickets_sold_notification(event)
            print(f"Уведомление отправлено организатору: {event.organizer.email}")
        except Exception as e:
            print(f"Ошибка отправки уведомления: {e}")


if __name__ == "__main__":
    event_id = int(sys.argv[1]) if len(sys.argv) > 1 else 374
    buy_all_tickets(event_id)
