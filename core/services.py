# -*- coding: utf-8 -*-
"""
Сервисы для атомарного бронирования билетов.
Защищают от race condition при одновременной покупке.
"""

import logging
from django.db import transaction, models as db_models
from django.core.exceptions import PermissionDenied
from django.utils import timezone
from datetime import timedelta

logger = logging.getLogger('ticket_purchase')


class TicketReservationError(Exception):
    """Исключение при ошибке бронирования билетов."""
    pass


def reserve_tickets(ticket_id, quantity, pre_reservation_check=None, **order_fields):
    """
    Атомарное бронирование билетов.
    
    Использует двухуровневую защиту:
    1. Redis-блокировка на весь процесс (глобальная для этого билета)
    2. SELECT FOR UPDATE внутри транзакции (для защиты от двойных обновлений БД)
    
    Args:
        ticket_id: ID билета
        quantity: Количество билетов
        **order_fields: Поля для создания заказа (ticket, participant_data, total_price, payment_status, ...)
    
    Returns:
        Order: Созданный заказ
    
    Raises:
        TicketReservationError: Если билетов недостаточно
    """
    from core.models import Ticket, Order, Event

    if quantity <= 0:
        raise TicketReservationError("Количество билетов должно быть больше нуля.")
    
    # Пытаемся получить Redis-блокировку
    lock = None
    try:
        from core.redis_utils import redis_lock
        lock = redis_lock(f"ticket_{ticket_id}_lock", timeout=30, blocking_timeout=5)
        lock.__enter__()
    except Exception as e:
        logger.warning("[reserve_tickets] Redis-блокировка недоступна: %s", e)
    
    try:
        with transaction.atomic():
            event_id = Ticket.objects.values_list("event_id", flat=True).get(pk=ticket_id)
            event = Event.objects.select_for_update().get(pk=event_id)
            if event.status != "active" or event.date_time <= timezone.now():
                raise TicketReservationError("Продажа билетов на это мероприятие закрыта.")
            if pre_reservation_check:
                pre_reservation_check()

            # Блокируем строку билета в БД (вторая линия защиты)
            ticket = Ticket.objects.select_for_update().select_related("event").get(pk=ticket_id)
            if ticket.event_id != event.pk:
                raise TicketReservationError("Билет не относится к доступному мероприятию.")

            if quantity < ticket.min_quantity:
                raise TicketReservationError(
                    f"Минимальное количество билетов этого типа: {ticket.min_quantity}."
                )
            if ticket.price < 0:
                raise TicketReservationError("У билета указана некорректная цена.")
            if (ticket.price == 0) != (order_fields.get("payment_status") == "succeeded"):
                raise TicketReservationError(
                    "Цена билета изменилась. Обновите страницу и попробуйте снова."
                )
            
            # Проверяем доступность
            if not ticket._check_availability(quantity):
                available = ticket.get_available_count()
                logger.error(
                    "[reserve_tickets] Билетов недостаточно",
                    extra={
                        'ticket_id': ticket_id,
                        'requested': quantity,
                        'available': available,
                        'event_id': ticket.event_id
                    }
                )
                raise TicketReservationError(
                    f"Билетов недостаточно. Запрошено: {quantity}, доступно: {available}"
                )
            
            # Создаём заказ (quantity уже передан в order_fields, но переопределяем)
            order_fields["total_price"] = ticket.price * quantity
            order = Order.objects.create(
                ticket=ticket,
                quantity=quantity,
                **order_fields
            )
            
            # Атомарно декрементируем available_quantity
            updated = Ticket.objects.filter(
                pk=ticket_id,
                available_quantity__gte=quantity
            ).update(available_quantity=db_models.F('available_quantity') - quantity)
            
            if updated == 0:
                order.delete()
                raise TicketReservationError("Билеты закончились. Попробуйте позже.")
            
            # Считаем реальное remaining после update, а не из старого значения
            remaining = Ticket.objects.filter(pk=ticket_id).values_list('available_quantity', flat=True).first()
            logger.info(
                "[reserve_tickets] Билеты успешно забронированы",
                extra={
                    'order_id': order.id,
                    'ticket_id': ticket_id,
                    'quantity': quantity,
                    'remaining': remaining
                }
            )
            
            # Проверяем, все ли билеты мероприятия проданы.
            # Уведомление отправляем ПОСЛЕ коммита транзакции.
            event = ticket.event
            if event.has_all_tickets_sold:
                def _notify_all_sold(event_id=event.id):
                    try:
                        from partner_app.views.events import send_partner_all_tickets_sold_notification
                        ev = Event.objects.get(id=event_id)
                        send_partner_all_tickets_sold_notification(ev)
                        logger.info(
                            "[reserve_tickets] Отправлено уведомление о продаже всех билетов: event_id=%s",
                            event_id
                        )
                    except Exception as e:
                        logger.error(
                            "[reserve_tickets] Ошибка отправки уведомления о продаже всех билетов: %s",
                            e, exc_info=True
                        )
                transaction.on_commit(_notify_all_sold)
            
            return order
    
    finally:
        if lock:
            try:
                lock.__exit__(None, None, None)
            except Exception as e:
                logger.warning("[reserve_tickets] Ошибка освобождения блокировки: %s", e)


def bulk_reserve_tickets(
    event_id,
    tickets_data,
    participant_data,
    payment_status,
    pre_reservation_check=None,
    **extra_fields
):
    """
    Атомарное бронирование нескольких типов билетов за один заказ (bulk-buy).
    
    Args:
        event_id: ID мероприятия
        tickets_data: Список словарей [{'id': ticket_id, 'quantity': qty}, ...]
        participant_data: Словарь с данными участника
        payment_status: Статус платежа
        **extra_fields: Дополнительные поля для заказов
    
    Returns:
        list[Order]: Список созданных заказов
    
    Raises:
        TicketReservationError: Если каких-то билетов недостаточно
    """
    from core.models import Ticket, Order, Event
    
    if not tickets_data:
        raise TicketReservationError("Нет билетов для бронирования")
    
    # Извлекаем список ID билетов для блокировок
    normalized_items = []
    for item in tickets_data:
        if not isinstance(item, dict):
            raise TicketReservationError("Некорректные данные билетов.")
        ticket_id = item.get("id")
        quantity = item.get("quantity")
        valid_ticket_id = (
            type(ticket_id) is int
            or isinstance(ticket_id, str)
            and ticket_id.strip().isdecimal()
        )
        valid_quantity = (
            type(quantity) is int
            or isinstance(quantity, str)
            and quantity.strip().isdecimal()
        )
        if not valid_ticket_id or not valid_quantity:
            raise TicketReservationError("Некорректные данные билетов.")
        normalized_items.append(
            {"id": int(ticket_id), "quantity": int(quantity)}
        )

    if any(item["quantity"] <= 0 for item in normalized_items):
        raise TicketReservationError("Количество билетов должно быть больше нуля.")

    ticket_ids = [item["id"] for item in normalized_items]
    if len(ticket_ids) != len(set(ticket_ids)):
        raise TicketReservationError("Тип билета указан несколько раз.")
    ticket_ids.sort()
    normalized_items.sort(key=lambda item: item["id"])
    if not ticket_ids:
        raise TicketReservationError("Нет билетов для бронирования")
    
    # Создаём список блокировок
    locks = []
    try:
        from core.redis_utils import redis_lock
        for tid in ticket_ids:
            lock = redis_lock(f"ticket_{tid}_lock", timeout=30, blocking_timeout=5)
            lock.__enter__()
            locks.append(lock)
    except Exception as e:
        logger.warning("[bulk_reserve_tickets] Redis-блокировки недоступны: %s", e)
    
    try:
        with transaction.atomic():
            event = Event.objects.select_for_update().get(pk=event_id)
            if event.status != "active" or event.date_time <= timezone.now():
                raise TicketReservationError("Продажа билетов на это мероприятие закрыта.")
            if pre_reservation_check:
                pre_reservation_check()

            orders = []
            
            for item in normalized_items:
                ticket_id = item['id']
                quantity = item['quantity']
                
                # Блокируем и проверяем каждый билет
                ticket = Ticket.objects.select_for_update().select_related("event").filter(
                    pk=ticket_id,
                    event_id=event_id,
                ).first()
                if ticket is None:
                    raise TicketReservationError("Билет не относится к выбранному мероприятию.")

                if quantity < ticket.min_quantity:
                    raise TicketReservationError(
                        f"Минимальное количество билетов типа «{ticket.name}»: "
                        f"{ticket.min_quantity}."
                    )
                if ticket.price < 0:
                    raise TicketReservationError("У билета указана некорректная цена.")
                if (ticket.price == 0) != (payment_status == "succeeded"):
                    raise TicketReservationError(
                        f"Цена билета «{ticket.name}» изменилась. Обновите страницу и попробуйте снова."
                    )
                
                if not ticket._check_availability(quantity):
                    available = ticket.get_available_count()
                    logger.error(
                        "[bulk_reserve_tickets] Билетов недостаточно",
                        extra={
                            'ticket_id': ticket_id,
                            'requested': quantity,
                            'available': available,
                            'event_id': event_id
                        }
                    )
                    raise TicketReservationError(
                        f"Билет «{ticket.name}» недоступен. Запрошено: {quantity}, доступно: {available}"
                    )
                
                # Рассчитываем цену
                total_price = ticket.price * quantity
                
                # Создаём заказ
                order = Order.objects.create(
                    ticket=ticket,
                    participant_data=participant_data,
                    total_price=total_price,
                    quantity=quantity,
                    payment_status=payment_status,
                    **extra_fields
                )
                orders.append(order)
                
                # Атомарно декрементируем количество
                updated = Ticket.objects.filter(
                    pk=ticket_id,
                    available_quantity__gte=quantity
                ).update(available_quantity=db_models.F('available_quantity') - quantity)
                
                if updated == 0:
                    order.delete()
                    raise TicketReservationError("Билеты закончились. Попробуйте позже.")
            
            logger.info(
                "[bulk_reserve_tickets] Билеты успешно забронированы",
                extra={
                    'event_id': event_id,
                    'orders_count': len(orders),
                    'ticket_ids': ticket_ids
                }
            )
            
            # Проверяем, все ли билеты мероприятия проданы.
            # Уведомление отправляем ПОСЛЕ коммита транзакции.
            def _notify_all_sold_bulk(event_id=event_id):
                try:
                    from partner_app.views.events import send_partner_all_tickets_sold_notification
                    ev = Event.objects.get(id=event_id)
                    if ev.has_all_tickets_sold:
                        send_partner_all_tickets_sold_notification(ev)
                        logger.info(
                            "[bulk_reserve_tickets] Отправлено уведомление о продаже всех билетов: event_id=%s",
                            event_id
                        )
                except Event.DoesNotExist:
                    pass
                except Exception as e:
                    logger.error(
                        "[bulk_reserve_tickets] Ошибка отправки уведомления: %s",
                        e, exc_info=True
                    )
            transaction.on_commit(_notify_all_sold_bulk)
            
            return orders
    
    finally:
        for lock in locks:
            try:
                lock.__exit__(None, None, None)
            except Exception as e:
                logger.warning("[bulk_reserve_tickets] Ошибка освобождения блокировки: %s", e)


def cancel_unpaid_order(order_id):
    """Atomically cancel an unpaid order and return its tickets to inventory."""
    from core.models import Order, RobokassaPayment, Ticket

    with transaction.atomic():
        candidate = Order.objects.filter(pk=order_id).values("payment_id").first()
        if candidate is None:
            return False

        payment_id = candidate["payment_id"]
        payment = None
        if payment_id:
            try:
                payment = RobokassaPayment.objects.select_for_update().filter(
                    pk=int(payment_id)
                ).first()
            except (TypeError, ValueError):
                logger.warning(
                    "[cancel_unpaid_order] Некорректный payment_id у заказа %s",
                    order_id,
                )

        order = Order.objects.select_for_update().filter(pk=order_id).first()
        if (
            order is None
            or order.payment_status not in ("reserved", "pending")
            or order.is_paid
            or order.payment_id != payment_id
        ):
            return False
        if payment and payment.status == "succeeded":
            return False

        ticket = Ticket.objects.select_for_update().get(pk=order.ticket_id)
        if payment and payment.status == "pending":
            payment.status = "canceled"
            payment.save(update_fields=["status", "updated_at"])
        order.payment_status = "canceled"
        order.is_paid = False
        order.save(update_fields=["payment_status", "is_paid"])
        ticket.available_quantity += order.quantity
        ticket.save(update_fields=["available_quantity"])
        return True
