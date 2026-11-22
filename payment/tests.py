import base64
import hashlib
import hmac
import json
from io import BytesIO
from types import SimpleNamespace
from urllib.parse import parse_qs, quote_plus, unquote_plus, urlparse
from unittest.mock import patch

from django.test import SimpleTestCase, override_settings

from payment.robokassa import (
    _make_refund_jwt,
    build_payment_url,
    build_receipt,
    create_refund,
    verify_result_signature,
)


@override_settings(
    ROBOKASSA_MERCHANT_LOGIN="test-shop",
    ROBOKASSA_PASSWORD1="password-one",
    ROBOKASSA_PASSWORD2="password-two",
    ROBOKASSA_PASSWORD3="password-three",
    ROBOKASSA_HASH_ALGORITHM="MD5",
    ROBOKASSA_TEST_MODE=True,
    ROBOKASSA_SNO="usn_income",
    ROBOKASSA_TICKET_TAX="vat10",
)
class RobokassaIntegrationTests(SimpleTestCase):
    def test_payment_url_contains_amount_invoice_and_valid_signature(self):
        url = build_payment_url(42, "125.5", "Event ticket", "buyer@example.com")
        params = parse_qs(urlparse(url).query)

        self.assertEqual(params["MerchantLogin"], ["test-shop"])
        self.assertEqual(params["OutSum"], ["125.50"])
        self.assertEqual(params["InvId"], ["42"])
        self.assertEqual(params["IsTest"], ["1"])
        expected = hashlib.md5(
            b"test-shop:125.50:42:password-one"
        ).hexdigest().upper()
        self.assertEqual(params["SignatureValue"], [expected])

    def test_receipt_is_included_in_payment_signature(self):
        receipt = {
            "sno": "usn_income",
            "items": [{
                "name": "Билет",
                "quantity": 1,
                "sum": 125.5,
                "tax": "vat10",
            }],
        }
        url = build_payment_url(42, "125.50", "Event ticket", receipt=receipt)
        params = parse_qs(urlparse(url).query)
        receipt_string = json.dumps(receipt, ensure_ascii=False, separators=(",", ":"))
        signature_base = (
            f"test-shop:125.50:42:{quote_plus(receipt_string)}:password-one"
        )
        expected = hashlib.md5(signature_base.encode("utf-8")).hexdigest().upper()

        self.assertEqual(json.loads(unquote_plus(params["Receipt"][0])), receipt)
        self.assertEqual(params["SignatureValue"], [expected])

    def test_build_receipt_uses_confirmed_tax_settings(self):
        order = SimpleNamespace(
            pk=7,
            quantity=2,
            total_price="246.00",
            ticket=SimpleNamespace(name="Конференция"),
        )

        receipt, order_items = build_receipt([order])

        self.assertEqual(receipt["sno"], "usn_income")
        self.assertEqual(receipt["items"][0]["tax"], "vat10")
        self.assertEqual(receipt["items"][0]["quantity"], 2)
        self.assertEqual(receipt["items"][0]["cost"], 123.0)
        self.assertEqual(order_items["7"], receipt["items"][0])

    def test_refund_jwt_uses_password3_hs256_signature(self):
        token = _make_refund_jwt({"OpKey": "operation-key", "RefundSum": 10.0})
        header, payload, signature = token.split(".")
        signing_input = f"{header}.{payload}".encode("ascii")
        expected_signature = hmac.new(
            b"password-three", signing_input, hashlib.sha256
        ).digest()
        decoded_payload = base64.urlsafe_b64decode(
            payload + "=" * (-len(payload) % 4)
        )

        self.assertEqual(
            base64.urlsafe_b64decode(signature + "=" * (-len(signature) % 4)),
            expected_signature,
        )
        self.assertEqual(json.loads(decoded_payload)["OpKey"], "operation-key")

    @patch("payment.robokassa.urlopen")
    def test_partial_refund_posts_amount_and_invoice_items(self, mocked_urlopen):
        mocked_urlopen.return_value = BytesIO(
            b'{"success":true,"requestId":"refund-123"}'
        )
        item = {
            "Name": "Билет",
            "Quantity": 1,
            "Cost": 123.0,
            "Tax": "vat10",
            "PaymentMethod": "full_payment",
            "PaymentObject": "service",
        }

        result = create_refund("operation-key", "123.00", [item])

        request = mocked_urlopen.call_args.args[0]
        payload = request.data.decode("ascii").split(".")[1]
        payload += "=" * (-len(payload) % 4)
        decoded_payload = json.loads(base64.urlsafe_b64decode(payload))
        self.assertEqual(request.method, "POST")
        self.assertEqual(decoded_payload["RefundSum"], 123.0)
        self.assertEqual(decoded_payload["InvoiceItems"], [item])
        self.assertEqual(result["requestId"], "refund-123")

    def test_result_signature_sorts_custom_parameters(self):
        params = {
            "OutSum": "125.50",
            "InvId": "42",
            "Shp_z": "last",
            "Shp_a": "first",
        }
        signature_base = (
            "125.50:42:password-two:Shp_a=first:Shp_z=last"
        )
        params["SignatureValue"] = hashlib.md5(
            signature_base.encode("utf-8")
        ).hexdigest()

        self.assertTrue(verify_result_signature(params))
        params["OutSum"] = "125.51"
        self.assertFalse(verify_result_signature(params))
