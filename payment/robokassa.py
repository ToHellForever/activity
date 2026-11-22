import base64
import hashlib
import hmac
import json
import re
import xml.etree.ElementTree as ET
from decimal import Decimal, InvalidOperation
from urllib.error import HTTPError, URLError
from urllib.parse import quote_plus, urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.utils import timezone


PAYMENT_URL = "https://auth.robokassa.ru/Merchant/Index.aspx"
OPERATION_STATE_URL = (
    "https://auth.robokassa.ru/Merchant/WebService/Service.asmx/OpStateExt"
)
REFUND_CREATE_URL = "https://services.robokassa.ru/RefundService/Refund/Create"
REFUND_STATE_URL = "https://services.robokassa.ru/RefundService/Refund/GetState"


class RefundRejectedError(RuntimeError):
    """Robokassa explicitly rejected a refund request."""


def _setting(name):
    value = getattr(settings, name, None)
    if not value:
        raise ImproperlyConfigured(f"Не задана настройка {name}")
    return value


def _digest(value):
    algorithm = getattr(settings, "ROBOKASSA_HASH_ALGORITHM", "MD5").lower()
    try:
        digest = hashlib.new(algorithm)
    except ValueError as exc:
        raise ImproperlyConfigured(
            f"Неподдерживаемый ROBOKASSA_HASH_ALGORITHM: {algorithm}"
        ) from exc
    digest.update(value.encode("utf-8"))
    return digest.hexdigest().upper()


def _amount_string(amount):
    try:
        value = Decimal(str(amount)).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("Некорректная сумма платежа") from exc
    if value <= 0:
        raise ValueError("Сумма платежа должна быть больше нуля")
    return format(value, ".2f")


def build_payment_url(
    inv_id,
    amount,
    description,
    email="",
    receipt=None,
    expiration_date=None,
):
    merchant_login = _setting("ROBOKASSA_MERCHANT_LOGIN")
    password1 = _setting("ROBOKASSA_PASSWORD1")
    amount_string = _amount_string(amount)
    inv_id = int(inv_id)
    if inv_id <= 0:
        raise ValueError("InvId должен быть положительным числом")

    signature_base = f"{merchant_login}:{amount_string}:{inv_id}"
    if receipt:
        receipt_string = quote_plus(
            json.dumps(receipt, ensure_ascii=False, separators=(",", ":"))
        )
        signature_base += f":{receipt_string}"
    else:
        receipt_string = None
    signature = _digest(f"{signature_base}:{password1}")
    params = {
        "MerchantLogin": merchant_login,
        "OutSum": amount_string,
        "InvId": str(inv_id),
        "Description": re.sub(r"[^\w\s-]", "", description)[:100],
        "Email": email,
        "Culture": "ru",
        "Encoding": "utf-8",
        "SignatureValue": signature,
    }
    if receipt_string:
        params["Receipt"] = receipt_string
    if expiration_date:
        expiration_moscow = timezone.localtime(
            expiration_date,
            ZoneInfo("Europe/Moscow"),
        )
        params["ExpirationDate"] = expiration_moscow.strftime("%Y-%m-%dT%H:%M")
    if getattr(settings, "ROBOKASSA_TEST_MODE", False):
        params["IsTest"] = "1"
    return f"{PAYMENT_URL}?{urlencode(params)}"


def build_receipt(orders):
    """Build the Robokassa receipt for the supplied orders."""
    items = []
    order_items = {}
    tax = getattr(settings, "ROBOKASSA_TICKET_TAX", "vat10")
    for order in orders:
        quantity = int(order.quantity)
        if quantity <= 0:
            raise ValueError("Количество билетов в заказе должно быть больше нуля")
        total = Decimal(str(order.total_price)).quantize(Decimal("0.01"))
        unit_cost = (total / quantity).quantize(Decimal("0.01"))
        if unit_cost * quantity != total:
            raise ValueError(
                f"Сумма заказа #{order.pk} не делится на стоимость билета до копеек"
            )
        name = (order.ticket.name or "Билет")[:128]
        item = {
            "name": name,
            "quantity": quantity,
            "cost": float(unit_cost),
            "sum": float(total),
            "payment_method": "full_payment",
            "payment_object": "service",
            "tax": tax,
        }
        items.append(item)
        order_items[str(order.pk)] = item

    receipt = {
        "sno": getattr(settings, "ROBOKASSA_SNO", "usn_income"),
        "items": items,
    }
    return receipt, order_items


def _b64url(value):
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _make_refund_jwt(payload):
    password3 = _setting("ROBOKASSA_PASSWORD3")
    header = _b64url(b'{"alg":"HS256","typ":"JWT"}')
    body = _b64url(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode(
            "utf-8"
        )
    )
    unsigned_token = f"{header}.{body}"
    signature = hmac.new(
        password3.encode("utf-8"),
        unsigned_token.encode("ascii"),
        hashlib.sha256,
    ).digest()
    return f"{unsigned_token}.{_b64url(signature)}"


def create_refund(op_key, amount, items, full_refund=False):
    payload = {"OpKey": op_key, "InvoiceItems": items}
    if not full_refund:
        payload["RefundSum"] = float(_amount_string(amount))
    token = _make_refund_jwt(payload)
    request = Request(
        REFUND_CREATE_URL,
        data=token.encode("ascii"),
        headers={"Content-Type": "text/plain; charset=utf-8"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=15) as response:
            result = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise RuntimeError("Не удалось создать возврат в Robokassa") from exc
    if not result.get("success") or not result.get("requestId"):
        raise RefundRejectedError(
            f"Robokassa отклонила возврат: {result.get('message') or 'неизвестная ошибка'}"
        )
    return result


def get_refund_status(request_id):
    query = urlencode({"id": request_id})
    try:
        with urlopen(f"{REFUND_STATE_URL}?{query}", timeout=10) as response:
            result = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise RuntimeError("Не удалось получить статус возврата Robokassa") from exc
    if result.get("requestId") != request_id or not result.get("label"):
        raise RuntimeError(
            f"Robokassa вернула некорректный статус возврата: {result.get('message') or 'нет статуса'}"
        )
    return result


def verify_result_signature(params):
    out_sum = params.get("OutSum")
    inv_id = params.get("InvId") or params.get("InvoiceID")
    signature = params.get("SignatureValue", "")
    if not out_sum or not inv_id or not signature:
        return False

    password2 = _setting("ROBOKASSA_PASSWORD2")
    user_params = sorted(
        (key, value)
        for key, value in params.items()
        if key.startswith("Shp_")
    )
    signature_base = f"{out_sum}:{inv_id}:{password2}"
    signature_base += "".join(f":{key}={value}" for key, value in user_params)
    return hmac.compare_digest(_digest(signature_base).casefold(), signature.casefold())


def get_operation_details(inv_id):
    merchant_login = _setting("ROBOKASSA_MERCHANT_LOGIN")
    password2 = _setting("ROBOKASSA_PASSWORD2")
    inv_id = str(int(inv_id))
    signature = _digest(f"{merchant_login}:{inv_id}:{password2}")
    query = urlencode({
        "MerchantLogin": merchant_login,
        "InvoiceID": inv_id,
        "Signature": signature,
    })
    try:
        with urlopen(f"{OPERATION_STATE_URL}?{query}", timeout=10) as response:
            root = ET.fromstring(response.read())
    except (URLError, ET.ParseError) as exc:
        raise RuntimeError("Не удалось получить статус операции Робокассы") from exc

    result_element = next(
        (element for element in root.iter() if element.tag.rsplit("}", 1)[-1] == "Result"),
        None,
    )
    state_element = next(
        (element for element in root.iter() if element.tag.rsplit("}", 1)[-1] == "State"),
        None,
    )
    result_code = next(
        (
            element.text
            for element in result_element or ()
            if element.tag.rsplit("}", 1)[-1] == "Code"
        ),
        None,
    )
    if result_code != "0":
        raise RuntimeError(
            f"Робокасса вернула ошибку проверки операции: {result_code}"
        )
    try:
        state_code = next(
            element.text
            for element in state_element or ()
            if element.tag.rsplit("}", 1)[-1] == "Code"
        )
        operation_key = next(
            element.text
            for element in root.iter()
            if element.tag.rsplit("}", 1)[-1].casefold() in ("opkey", "operationkey")
        )
        if not operation_key:
            raise RuntimeError("В ответе Робокассы отсутствует ключ операции")
        return {"state": int(state_code), "op_key": operation_key}
    except (TypeError, ValueError) as exc:
        raise RuntimeError("Некорректный ответ о состоянии операции Robokassa") from exc
    except StopIteration as exc:
        raise RuntimeError("В ответе Robokassa отсутствуют данные операции") from exc


def get_operation_state(inv_id):
    return get_operation_details(inv_id)["state"]
