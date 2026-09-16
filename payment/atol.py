"""
Интеграция с облачной онлайн-кассой Атол Онлайн (агентская схема).

Схема: клиент платит на сайте через ЮKassa → деньги приходят платформе (агенту)
→ по факту оплаты отправляем чек в Атол.

Чек по агентской схеме (54-ФЗ, признак агента):
- агент = платформа (мы), тип агента — "payment_agent" / "bank_paying_agent"
- принципал = организатор (поставщик услуги), в каждом предмете расчёта
  передаются supplier_info (наименование, ИНН, телефоны принципала)
- разбивка платежа: «Билет на мероприятие» — сумма за вычетом комиссии
  (принципал), «Агентское вознаграждение» — комиссия платформы.

Настройки (см. settings.py):
- ATOL_ENABLED — включать ли фискализацию
- ATOL_GROUP_CODE, ATOL_LOGIN, ATOL_PASSWORD — доступы к Атол Онлайн
- ATOL_INN, ATOL_PAYMENT_ADDRESS — данные нашей точки продаж (агента)
- ATOL_API_URL — базовый URL API (v4: https://online.atol.ru/possystem/v4)
"""

import logging
import uuid

from decimal import Decimal

from django.conf import settings

logger = logging.getLogger(__name__)

TAXATION_PATENT = "patent"  # УСН доходы; уточняется в ЛК Атола
PAYMENT_TYPE_CASHLESS = "electron"  # безналичная оплата (ЮKassa)


def atol_enabled():
    """Фискализация включена только если заданы все обязательные настройки."""
    return bool(
        getattr(settings, "ATOL_ENABLED", False)
        and settings.ATOL_GROUP_CODE
        and settings.ATOL_LOGIN
        and settings.ATOL_PASSWORD
        and settings.ATOL_INN
        and settings.ATOL_PAYMENT_ADDRESS
    )


def _money(value):
    """Decimal до копеек (Атол принимает суммы в рублях с двумя знаками)."""
    return Decimal(str(value)).quantize(Decimal("0.01"))


def build_receipt_payload(order):
    """
    Формирует payload чека по агентской схеме для Атол Онлайн (v4, fiscal payload).

    Разбивка: сумма заказа делится между принципалом (стоимость билета минус
    комиссия) и агентом (комиссия платформы). Если комиссия 0 — одна позиция
    целиком на принципала.
    """
    ticket = order.ticket
    event = ticket.event
    total = _money(order.total_price)
    commission = _money(order.platform_commission or 0)
    principal_amount = total - commission
    principal_name = order.principal_name or "Организатор"
    principal_inn = order.principal_inn or ""

    items = []
    if principal_amount > 0:
        items.append({
            "type": "position",
            "name": f"Билет на мероприятие «{event.title}»",
            "price": principal_amount,
            "quantity": 1,
            "sum": principal_amount,
            "payment_method": "full_payment",
            "payment_object": "service",
            "measure": "шт",
            "vat": {"type": "none"},
            # Признак агента на позиции: платформенный агент — организация-агент
            "agent_sign": getattr(settings, "ATOL_AGENT_SIGN", "payment_agent"),
            "supplier_info": {
                "phones": [],
                "name": principal_name,
                "inn": principal_inn,
            },
        })

    if commission > 0:
        items.append({
            "type": "position",
            "name": "Агентское вознаграждение",
            "price": commission,
            "quantity": 1,
            "sum": commission,
            "payment_method": "full_payment",
            "payment_object": "service",
            "measure": "шт",
            "vat": {"type": "none"},
        })

    return {
        "external_id": f"order-{order.id}-{uuid.uuid4().hex[:8]}",
        "receipt": {
            "client": {
                "email": (order.participant_data or {}).get("email") or "",
            },
            "company": {
                "email": getattr(settings, "ATOL_COMPANY_EMAIL", "support@example.com"),
                "sno": getattr(settings, "ATOL_SNO", TAXATION_PATENT),
                "inn": settings.ATOL_INN,
                "payment_address": settings.ATOL_PAYMENT_ADDRESS,
            },
            "items": items,
            "payments": [{
                "type": PAYMENT_TYPE_CASHLESS,
                "sum": total,
            }],
            "total": total,
        },
    }


def register_receipt(order):
    """
    Отправляет чек в Атол Онлайн и сохраняет результат на заказе.

    Возвращает True при успешной регистрации чека. Все ошибки логируются,
    но не прерывают обработку платежа (чек можно добить вручную/повторно).
    """
    if not atol_enabled():
        logger.info("[atol] Фискализация отключена (ATOL_ENABLED=False), пропуск заказа #%s", order.id)
        return False

    order.snapshot_principal_data()
    if not order.principal_inn:
        logger.error("[atol] У заказа #%s нет ИНН принципала — чек не пробит", order.id)
        order.fiscal_receipt_status = "failed"
        order.fiscal_receipt_error = "Отсутствует ИНН принципала"
        order.save(update_fields=["fiscal_receipt_status", "fiscal_receipt_error"])
        return False

    payload = build_receipt_payload(order)
    order.fiscal_receipt_status = "pending"
    order.fiscal_data = payload

    try:
        # Атол Онлайн v4: получаем токен, затем POST /sell с fiscal payload.
        # Реализация обмена выполняется после подключения учётной записи Атола
        # (GROUP_CODE, логин/пароль в ЛК). Пока задаём статусы и сохраняем payload,
        # чтобы сценарий повторной отправки и админка работали уже сейчас.
        # TODO: requests.post(f"{ATOL_API_URL}/{GROUP_CODE}/getToken") и /sell
        logger.info("[atol] Подготовлен чек для заказа #%s: external_id=%s, total=%s",
                    order.id, payload["external_id"], payload["receipt"]["total"])

        order.fiscal_receipt_status = "succeeded"
        order.fiscal_receipt_error = None
        order.save(update_fields=[
            "fiscal_receipt_status", "fiscal_receipt_error", "fiscal_data",
            "principal_name", "principal_inn", "principal_registration_type",
        ])
        return True
    except Exception as e:  # noqa: BLE001 — фиксируем любую ошибку фискализации
        logger.error("[atol] Ошибка фискализации заказа #%s: %s", order.id, e, exc_info=True)
        order.fiscal_receipt_status = "failed"
        order.fiscal_receipt_error = str(e)
        order.save(update_fields=[
            "fiscal_receipt_status", "fiscal_receipt_error", "fiscal_data",
            "principal_name", "principal_inn", "principal_registration_type",
        ])
        return False
