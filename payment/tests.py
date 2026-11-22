import base64
import hashlib
import hmac
import json
from datetime import timedelta
from decimal import Decimal
from io import BytesIO
from types import SimpleNamespace
from urllib.parse import parse_qs, quote_plus, unquote_plus, urlparse
from unittest.mock import patch
from zoneinfo import ZoneInfo

from django.contrib.auth import get_user_model
from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from core.models import Event, Order, OrderTicket, RobokassaPayment, RobokassaRefund, Ticket
from core.tasks import check_robokassa_refunds, check_unpaid_tickets
from payment.views import robokassa_result
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

    def test_expiration_date_is_sent_without_changing_signature(self):
        expiration_date = timezone.now() + timedelta(minutes=15)
        url = build_payment_url(
            42,
            "125.50",
            "Event ticket",
            expiration_date=expiration_date,
        )
        params = parse_qs(urlparse(url).query)
        expected = timezone.localtime(
            expiration_date,
            ZoneInfo("Europe/Moscow"),
        ).strftime("%Y-%m-%dT%H:%M")
        expected_signature = hashlib.md5(
            b"test-shop:125.50:42:password-one"
        ).hexdigest().upper()

        self.assertEqual(params["ExpirationDate"], [expected])
        self.assertEqual(params["SignatureValue"], [expected_signature])

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


@override_settings(
    ROBOKASSA_TEST_MODE=False,
    ROBOKASSA_PASSWORD3="password-three",
)
class RobokassaBulkRefundTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(
            username="buyer",
            email="buyer@example.com",
            password="password",
        )
        self.event = Event.objects.create(
            organizer=self.user,
            title="Тестовое событие",
            description="Описание",
            date_time=timezone.now() + timedelta(days=1),
            district="",
            metro="",
        )
        self.ticket_a = Ticket.objects.create(
            event=self.event,
            name="Стандарт",
            price="10.00",
            available_quantity=0,
        )
        self.ticket_b = Ticket.objects.create(
            event=self.event,
            name="VIP",
            price="20.00",
            available_quantity=0,
        )
        self.order_a = self._create_order(self.ticket_a, 1, "10.00")
        self.order_b = self._create_order(self.ticket_b, 2, "40.00")
        self.payment = RobokassaPayment.objects.create(
            amount="50.00",
            status="succeeded",
            operation_key="operation-key",
            receipt_data={
                "order_items": {
                    str(self.order_a.pk): {
                        "name": "Стандарт",
                        "cost": 10.0,
                        "tax": "vat10",
                        "payment_method": "full_payment",
                        "payment_object": "service",
                    },
                    str(self.order_b.pk): {
                        "name": "VIP",
                        "cost": 20.0,
                        "tax": "vat10",
                        "payment_method": "full_payment",
                        "payment_object": "service",
                    },
                }
            },
        )
        self.payment.orders.add(self.order_a, self.order_b)
        Order.objects.filter(pk__in=[self.order_a.pk, self.order_b.pk]).update(
            payment_id=str(self.payment.pk)
        )
        self.client.force_login(self.user)

    def _create_order(self, ticket, quantity, total_price):
        order = Order.objects.create(
            ticket=ticket,
            participant_data={"email": self.user.email},
            total_price=total_price,
            quantity=quantity,
            payment_status="succeeded",
            is_paid=True,
        )
        return order

    @patch("payment.views.create_refund", return_value={"requestId": "refund-123"})
    def test_refund_all_orders_in_one_payment(self, mocked_create_refund):
        response = self.client.post(
            reverse(
                "visitor:refund_ticket",
                args=[self.order_a.pk, self.order_a.tickets.first().pk],
            ),
            {"refund_scope": "whole_payment"},
        )

        self.assertEqual(response.status_code, 202)
        mocked_create_refund.assert_called_once()
        _, amount, items = mocked_create_refund.call_args.args
        self.assertEqual(amount, Decimal("50.00"))
        self.assertEqual(
            [(item["Name"], item["Quantity"]) for item in items],
            [("Стандарт", 1), ("VIP", 2)],
        )
        refund = RobokassaRefund.objects.get(request_id="refund-123")
        self.assertEqual(refund.orders.count(), 2)
        self.assertIsNone(refund.order_ticket_id)

        with patch(
            "payment.robokassa.get_refund_status",
            return_value={"label": "finished", "amount": "50.00"},
        ):
            check_robokassa_refunds()

        self.order_a.refresh_from_db()
        self.order_b.refresh_from_db()
        self.assertEqual(self.order_a.payment_status, "refunded")
        self.assertEqual(self.order_b.payment_status, "refunded")
        self.assertTrue(all(ticket.is_refunded for ticket in self.order_a.tickets.all()))
        self.assertTrue(all(ticket.is_refunded for ticket in self.order_b.tickets.all()))
        self.assertEqual(Ticket.objects.get(pk=self.ticket_a.pk).available_quantity, 1)
        self.assertEqual(Ticket.objects.get(pk=self.ticket_b.pk).available_quantity, 2)


@override_settings(
    ROBOKASSA_TEST_MODE=True,
    ROBOKASSA_PASSWORD2="password-two",
    ROBOKASSA_HASH_ALGORITHM="MD5",
)
class UnpaidRobokassaOrderExpiryTests(TestCase):
    def test_orders_expire_after_15_minutes_in_test_mode(self):
        user = get_user_model().objects.create_user(
            username="expiry-buyer",
            email="expiry@example.com",
            password="password",
        )
        event = Event.objects.create(
            organizer=user,
            title="Тестовое событие",
            description="Описание",
            date_time=timezone.now() + timedelta(days=1),
            district="",
            metro="",
        )
        expired_order = self._create_pending_order(event, user, "Истёк")
        recent_order = self._create_pending_order(event, user, "Недавний")
        recently_paid_invoice_order = self._create_pending_order(
            event,
            user,
            "Счёт ещё не истёк",
        )
        now = timezone.now()
        expired_at = now - timedelta(minutes=16)
        recent_at = now - timedelta(minutes=14)
        Order.objects.filter(pk=expired_order.pk).update(
            created_at=expired_at
        )
        Order.objects.filter(pk=recent_order.pk).update(
            created_at=recent_at
        )
        Order.objects.filter(pk=recently_paid_invoice_order.pk).update(
            created_at=expired_at
        )
        RobokassaPayment.objects.filter(
            pk=expired_order.payment_id
        ).update(created_at=expired_at)
        RobokassaPayment.objects.filter(
            pk=recent_order.payment_id
        ).update(created_at=recent_at)
        RobokassaPayment.objects.filter(
            pk=recently_paid_invoice_order.payment_id
        ).update(created_at=recent_at)

        with patch("django.core.mail.send_mail"):
            check_unpaid_tickets()

        expired_order.refresh_from_db()
        recent_order.refresh_from_db()
        recently_paid_invoice_order.refresh_from_db()
        self.assertEqual(expired_order.payment_status, "canceled")
        self.assertEqual(recent_order.payment_status, "pending")
        self.assertEqual(recently_paid_invoice_order.payment_status, "pending")
        self.assertEqual(expired_order.ticket.available_quantity, 1)
        self.assertEqual(recent_order.ticket.available_quantity, 0)
        self.assertEqual(recently_paid_invoice_order.ticket.available_quantity, 0)
        self.assertEqual(
            RobokassaPayment.objects.get(pk=expired_order.payment_id).status,
            "canceled",
        )
        signature = hashlib.md5(
            f"10.00:{expired_order.payment_id}:password-two".encode("utf-8")
        ).hexdigest()
        callback = RequestFactory().get(
            "/payment/robokassa/result/",
            {
                "OutSum": "10.00",
                "InvId": expired_order.payment_id,
                "SignatureValue": signature,
            },
        )
        self.assertEqual(robokassa_result(callback).status_code, 409)

    def _create_pending_order(self, event, user, ticket_name):
        ticket = Ticket.objects.create(
            event=event,
            name=ticket_name,
            price="10.00",
            available_quantity=0,
        )
        order = Order.objects.create(
            ticket=ticket,
            participant_data={"email": user.email},
            total_price="10.00",
            quantity=1,
            payment_status="pending",
        )
        payment = RobokassaPayment.objects.create(amount="10.00")
        payment.orders.add(order)
        order.payment_id = str(payment.pk)
        order.save(update_fields=["payment_id"])
        return order
