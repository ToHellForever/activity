import hashlib
import hmac
import re
import xml.etree.ElementTree as ET
from decimal import Decimal, InvalidOperation
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import urlopen

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


PAYMENT_URL = "https://auth.robokassa.ru/Merchant/Index.aspx"
OPERATION_STATE_URL = (
    "https://auth.robokassa.ru/Merchant/WebService/Service.asmx/OpStateExt"
)


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


def build_payment_url(inv_id, amount, description, email=""):
    merchant_login = _setting("ROBOKASSA_MERCHANT_LOGIN")
    password1 = _setting("ROBOKASSA_PASSWORD1")
    amount_string = _amount_string(amount)
    inv_id = int(inv_id)
    if inv_id <= 0:
        raise ValueError("InvId должен быть положительным числом")

    signature = _digest(f"{merchant_login}:{amount_string}:{inv_id}:{password1}")
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
    if getattr(settings, "ROBOKASSA_TEST_MODE", False):
        params["IsTest"] = "1"
    return f"{PAYMENT_URL}?{urlencode(params)}"


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


def get_operation_state(inv_id):
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
        return int(state_code)
    except (TypeError, ValueError) as exc:
        raise RuntimeError("В ответе Робокассы отсутствует код состояния") from exc
    except StopIteration as exc:
        raise RuntimeError("В ответе Робокассы отсутствует код состояния") from exc
