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


def reserve_tickets(ticket_id, quantity, **order_fields):
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
    from core.models import Ticket, Order
    
    # Пытаемся получить Redis-блокировку
    lock = None
    try:
        from core.redis_utils import redis_lock
        lock = redis_lock(f"ticket_{ticket_id}_lock", timeout=30, blocking_timeout=5)
        lock.__enter__()
    except Exception as e:
        logger.warning(f"[reserve_tickets] Redis-блокировка недоступна: {e}")
    
    try:
        with transaction.atomic():
            # Блокируем строку билета в БД (вторая линия защиты)
            ticket = Ticket.objects.select_for_update().get(pk=ticket_id)
            
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
            
            logger.info(
                "[reserve_tickets] Билеты успешно забронированы",
                extra={
                    'order_id': order.id,
                    'ticket_id': ticket_id,
                    'quantity': quantity,
                    'remaining': ticket.available_quantity - quantity
                }
            )
            
            return order
    
    finally:
        if lock:
            try:
                lock.__exit__(None, None, None)
            except Exception as e:
                logger.warning(f"[reserve_tickets] Ошибка освобождения блокировки: {e}")


def bulk_reserve_tickets(event_id, tickets_data, participant_data, payment_status, **extra_fields):
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
    from core.models import Ticket, Order
    
    # Собираем все ticket_id для блокировки
    ticket_ids = [item['id'] for item in tickets_data if item.get('quantity', 0) > 0]
    
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
        logger.warning(f"[bulk_reserve_tickets] Redis-блокировки недоступны: {e}")
    
    try:
        with transaction.atomic():
            orders = []
            
            for item in tickets_data:
                ticket_id = item['id']
                quantity = item.get('quantity', 0)
                
                if quantity <= 0:
                    continue
                
                # Блокируем и проверяем каждый билет
                ticket = Ticket.objects.select_for_update().get(pk=ticket_id)
                
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
            
            return orders
    
    finally:
        for lock in locks:
            try:
                lock.__exit__(None, None, None)
            except Exception as e:
                logger.warning(f"[bulk_reserve_tickets] Ошибка освобождения блокировки: {e}")
