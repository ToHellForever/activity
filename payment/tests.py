import base64
import hashlib
import hmac
import json
from datetime import timedelta
from decimal import Decimal
from io import BytesIO
from types import SimpleNamespace
from urllib.error import HTTPError
from urllib.parse import parse_qs, quote_plus, unquote_plus, urlparse
from unittest.mock import patch
from zoneinfo import ZoneInfo

from django.contrib.auth import get_user_model
from django.test import Client, RequestFactory, SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from core.models import Event, Order, OrderTicket, RobokassaPayment, RobokassaRefund, Ticket
from core.tasks import (
    check_robokassa_refunds,
    check_reserved_tickets,
    check_unpaid_tickets,
)
from payment.views import robokassa_result
from payment.robokassa import (
    REFUND_CREATE_URL,
    RefundRejectedError,
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
        token = json.loads(request.data.decode("utf-8"))
        payload = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        decoded_payload = json.loads(base64.urlsafe_b64decode(payload))
        self.assertEqual(request.method, "POST")
        self.assertEqual(request.get_header("Content-type"), "application/json")
        self.assertEqual(len(token.split(".")), 3)
        self.assertEqual(decoded_payload["RefundSum"], 123.0)
        self.assertEqual(decoded_payload["InvoiceItems"], [item])
        self.assertEqual(result["requestId"], "refund-123")

    @patch("payment.robokassa.urlopen")
    def test_refund_rejects_unsupported_request_content_type(self, mocked_urlopen):
        mocked_urlopen.side_effect = HTTPError(
            REFUND_CREATE_URL,
            415,
            "Unsupported Media Type",
            {},
            BytesIO(b"Unsupported Media Type"),
        )

        with self.assertRaisesRegex(RefundRejectedError, "HTTP 415"):
            create_refund("operation-key", "5.00", [])

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

    @patch(
        "payment.views.create_refund",
        side_effect=RefundRejectedError("Robokassa отклонила возврат (HTTP 400)"),
    )
    def test_rejected_refund_returns_client_error_not_bad_gateway(
        self,
        mocked_create_refund,
    ):
        response = self.client.post(
            reverse(
                "visitor:refund_ticket",
                args=[self.order_a.pk, self.order_a.tickets.first().pk],
            )
        )

        self.assertEqual(response.status_code, 400)
        mocked_create_refund.assert_called_once()
        refund = RobokassaRefund.objects.get(order_ticket=self.order_a.tickets.first())
        self.assertEqual(refund.status, "failed")
        self.assertIsNone(refund.request_id)

    def test_payment_success_page_displays_all_ticket_types(self):
        response = self.client.get(
            reverse("payment:payment_success", args=[self.order_a.pk])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Стандарт")
        self.assertContains(response, "VIP")
        self.assertContains(response, "Итого по оплате")
        self.assertEqual(response.context[0]["payment_amount"], Decimal("50.00"))


@override_settings(
    ROBOKASSA_MERCHANT_LOGIN="test-shop",
    ROBOKASSA_PASSWORD1="password-one",
    ROBOKASSA_TEST_MODE=True,
    ROBOKASSA_PASSWORD2="password-two",
    ROBOKASSA_HASH_ALGORITHM="MD5",
    ROBOKASSA_SNO="usn_income",
    ROBOKASSA_TICKET_TAX="vat10",
)
class TicketPurchaseFlowTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="purchase-buyer",
            email="purchase@example.com",
            password="password",
        )
        self.event = Event.objects.create(
            organizer=self.user,
            title="Открытое событие",
            description="Описание",
            date_time=timezone.now() + timedelta(days=3),
            district="",
            metro="",
            status="active",
        )
        self.ticket = Ticket.objects.create(
            event=self.event,
            name="Стандарт",
            price="10.00",
            available_quantity=4,
        )

    def _bulk_buy(self, event, tickets, **extra_data):
        data = {
            "tickets": tickets,
            "email": self.user.email,
            "consent_personal_data": True,
            **extra_data,
        }
        return self.client.post(
            reverse("payment:bulk_buy_tickets", args=[event.pk]),
            data=json.dumps(data),
            content_type="application/json",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

    def test_bulk_purchase_rejects_ticket_from_another_event(self):
        other_event = Event.objects.create(
            organizer=self.user,
            title="Другое событие",
            description="Описание",
            date_time=timezone.now() + timedelta(days=4),
            district="",
            metro="",
            status="active",
        )
        other_ticket = Ticket.objects.create(
            event=other_event,
            name="Чужой билет",
            price="10.00",
            available_quantity=2,
        )

        response = self._bulk_buy(
            self.event,
            [{"id": other_ticket.pk, "quantity": 1}],
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(Order.objects.count(), 0)
        other_ticket.refresh_from_db()
        self.assertEqual(other_ticket.available_quantity, 2)

    def test_bulk_purchase_creates_one_invoice_for_multiple_ticket_types(self):
        vip_ticket = Ticket.objects.create(
            event=self.event,
            name="VIP",
            price="20.00",
            available_quantity=2,
        )

        response = self._bulk_buy(
            self.event,
            [
                {"id": self.ticket.pk, "quantity": 1},
                {"id": vip_ticket.pk, "quantity": 1},
            ],
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["success"])
        self.assertIn("payment_url", payload)
        payment = RobokassaPayment.objects.get()
        self.assertEqual(payment.amount, Decimal("30.00"))
        self.assertEqual(payment.orders.count(), 2)
        self.assertEqual(Order.objects.count(), 2)
        self.ticket.refresh_from_db()
        vip_ticket.refresh_from_db()
        self.assertEqual(self.ticket.available_quantity, 3)
        self.assertEqual(vip_ticket.available_quantity, 1)

    def test_mixed_reservation_sends_each_email_once_without_invoice(self):
        self.event.allow_booking_without_payment = True
        self.event.save(update_fields=["allow_booking_without_payment"])
        free_ticket = Ticket.objects.create(
            event=self.event,
            name="Бесплатный",
            price="0.00",
            available_quantity=2,
        )

        with patch("payment.views._send_orders_confirmation_email") as free_email, patch(
            "payment.views.send_reservation_email"
        ) as reservation_email:
            response = self._bulk_buy(
                self.event,
                [
                    {"id": self.ticket.pk, "quantity": 1},
                    {"id": free_ticket.pk, "quantity": 1},
                ],
                reserve_without_payment=True,
            )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])
        free_email.assert_called_once()
        reservation_email.assert_called_once()
        self.assertEqual(RobokassaPayment.objects.count(), 0)
        self.assertEqual(
            set(Order.objects.values_list("payment_status", flat=True)),
            {"succeeded", "reserved"},
        )

    def test_bulk_purchase_rejects_nonpositive_quantity(self):
        response = self._bulk_buy(
            self.event,
            [{"id": self.ticket.pk, "quantity": 0}],
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(Order.objects.count(), 0)
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.available_quantity, 4)

    def test_bulk_purchase_rejects_fractional_quantity(self):
        response = self._bulk_buy(
            self.event,
            [{"id": self.ticket.pk, "quantity": 1.5}],
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(Order.objects.count(), 0)

    def test_bulk_purchase_enforces_ticket_minimum_quantity(self):
        self.ticket.min_quantity = 2
        self.ticket.save(update_fields=["min_quantity"])

        response = self._bulk_buy(
            self.event,
            [{"id": self.ticket.pk, "quantity": 1}],
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(Order.objects.count(), 0)
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.available_quantity, 4)

    @patch("payment.views._create_robokassa_payment", side_effect=RuntimeError("invalid merchant config"))
    def test_bulk_invoice_failure_releases_reserved_inventory(self, mocked_create_payment):
        response = self._bulk_buy(
            self.event,
            [{"id": self.ticket.pk, "quantity": 1}],
        )

        self.assertEqual(response.status_code, 502)
        mocked_create_payment.assert_called_once()
        order = Order.objects.get()
        self.assertEqual(order.payment_status, "canceled")
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.available_quantity, 4)

    def test_bulk_purchase_requires_csrf_token(self):
        client = Client(enforce_csrf_checks=True)
        response = client.post(
            reverse("payment:bulk_buy_tickets", args=[self.event.pk]),
            data=json.dumps({
                "tickets": [{"id": self.ticket.pk, "quantity": 1}],
                "email": self.user.email,
                "consent_personal_data": True,
            }),
            content_type="application/json",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(Order.objects.count(), 0)

    @patch("payment.views.send_reservation_email")
    def test_reservation_without_payment_does_not_create_invoice(self, mocked_email):
        self.event.allow_booking_without_payment = True
        self.event.save(update_fields=["allow_booking_without_payment"])
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("payment:create_payment", args=[self.ticket.pk]),
            {
                "name": "Покупатель",
                "email": self.user.email,
                "phone": "+70000000000",
                "quantity": "1",
                "reserve_without_payment": "on",
            },
        )

        self.assertEqual(response.status_code, 302)
        mocked_email.assert_called_once()
        order = Order.objects.get()
        self.assertEqual(order.payment_status, "reserved")
        self.assertIsNone(order.payment_id)
        self.assertEqual(RobokassaPayment.objects.count(), 0)
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.available_quantity, 3)

    @patch("payment.views._create_robokassa_payment", side_effect=RuntimeError("invalid merchant config"))
    def test_single_invoice_failure_releases_reserved_inventory(self, mocked_create_payment):
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("payment:create_payment", args=[self.ticket.pk]),
            {
                "name": "Покупатель",
                "email": self.user.email,
                "phone": "+70000000000",
                "quantity": "1",
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 400)
        mocked_create_payment.assert_called_once()
        order = Order.objects.get()
        self.assertEqual(order.payment_status, "canceled")
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.available_quantity, 4)

    def test_single_free_purchase_limit_counts_tickets_not_orders(self):
        free_ticket = Ticket.objects.create(
            event=self.event,
            name="Бесплатный",
            price="0.00",
            available_quantity=4,
        )
        Order.objects.create(
            ticket=free_ticket,
            participant_data={"email": self.user.email},
            total_price="0.00",
            quantity=1,
            payment_status="succeeded",
            is_paid=True,
        )
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("payment:create_payment", args=[free_ticket.pk]),
            {
                "name": "Покупатель",
                "email": self.user.email,
                "phone": "+70000000000",
                "quantity": "2",
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(Order.objects.count(), 1)
        free_ticket.refresh_from_db()
        self.assertEqual(free_ticket.available_quantity, 4)

    @patch("payment.views.send_reservation_email", side_effect=RuntimeError("mail unavailable"))
    def test_failed_reservation_email_releases_reserved_inventory(self, mocked_email):
        self.event.allow_booking_without_payment = True
        self.event.save(update_fields=["allow_booking_without_payment"])
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("payment:create_payment", args=[self.ticket.pk]),
            {
                "name": "Покупатель",
                "email": self.user.email,
                "phone": "+70000000000",
                "quantity": "1",
                "reserve_without_payment": "on",
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 400)
        order = Order.objects.get()
        self.assertEqual(order.payment_status, "canceled")
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.available_quantity, 4)

    def test_expired_reservation_cannot_create_payment(self):
        self.client.force_login(self.user)
        order = Order.objects.create(
            ticket=self.ticket,
            participant_data={"email": self.user.email},
            total_price="10.00",
            quantity=1,
            payment_status="reserved",
            payment_deadline=timezone.now() - timedelta(minutes=1),
        )

        response = self.client.get(
            reverse("payment:pay_reserved_order", args=[order.pk])
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(RobokassaPayment.objects.count(), 0)
        order.refresh_from_db()
        self.assertEqual(order.payment_status, "reserved")

    @patch("core.tasks.send_reservation_cancelation")
    def test_expired_reservation_is_released_once_and_invoice_canceled(self, mocked_email):
        Ticket.objects.filter(pk=self.ticket.pk).update(available_quantity=2)
        order = Order.objects.create(
            ticket=self.ticket,
            participant_data={"email": self.user.email},
            total_price="10.00",
            quantity=2,
            payment_status="reserved",
            payment_deadline=timezone.now() - timedelta(minutes=1),
        )
        payment = RobokassaPayment.objects.create(
            amount="10.00",
            status="pending",
        )
        payment.orders.add(order)
        order.payment_id = str(payment.pk)
        order.save(update_fields=["payment_id"])

        check_reserved_tickets()
        check_reserved_tickets()

        order.refresh_from_db()
        payment.refresh_from_db()
        self.ticket.refresh_from_db()
        self.assertEqual(order.payment_status, "canceled")
        self.assertEqual(payment.status, "canceled")
        self.assertEqual(self.ticket.available_quantity, 4)
        mocked_email.assert_called_once()
        signature = hashlib.md5(
            f"10.00:{payment.pk}:password-two".encode("utf-8")
        ).hexdigest()
        callback = RequestFactory().get(
            "/payment/robokassa/result/",
            {
                "OutSum": "10.00",
                "InvId": payment.pk,
                "SignatureValue": signature,
            },
        )
        self.assertEqual(robokassa_result(callback).status_code, 409)

    @patch("core.tasks.send_reservation_reminder")
    def test_reservation_reminder_is_sent_only_once(self, mocked_email):
        self.event.date_time = timezone.now() + timedelta(hours=47, minutes=30)
        self.event.save(update_fields=["date_time"])
        Order.objects.create(
            ticket=self.ticket,
            participant_data={"email": self.user.email},
            total_price="10.00",
            quantity=1,
            payment_status="reserved",
            payment_deadline=timezone.now() + timedelta(hours=12),
        )

        check_reserved_tickets()
        check_reserved_tickets()

        mocked_email.assert_called_once_with(Order.objects.get(), 48)

    def test_failed_robokassa_return_is_not_shown_as_successful_payment(self):
        order = Order.objects.create(
            ticket=self.ticket,
            participant_data={"email": self.user.email},
            total_price="10.00",
            quantity=1,
            payment_status="pending",
        )
        payment = RobokassaPayment.objects.create(amount="10.00")
        payment.orders.add(order)
        order.payment_id = str(payment.pk)
        order.save(update_fields=["payment_id"])

        response = self.client.get(
            reverse("payment:robokassa_fail"),
            {"InvId": payment.pk},
        )

        self.assertEqual(response.status_code, 302)
        page = self.client.get(response["Location"])
        self.assertContains(page, "Оплата не завершена")
        self.assertNotContains(page, "Оплата успешна!")

    def test_result_callback_rejects_amount_that_only_rounds_to_invoice_total(self):
        order = Order.objects.create(
            ticket=self.ticket,
            participant_data={"email": self.user.email},
            total_price="10.00",
            quantity=1,
            payment_status="pending",
        )
        payment = RobokassaPayment.objects.create(amount="10.00")
        payment.orders.add(order)
        order.payment_id = str(payment.pk)
        order.save(update_fields=["payment_id"])
        out_sum = "10.001"
        signature = hashlib.md5(
            f"{out_sum}:{payment.pk}:password-two".encode("utf-8")
        ).hexdigest()

        response = robokassa_result(RequestFactory().get(
            "/payment/robokassa/result/",
            {
                "OutSum": out_sum,
                "InvId": payment.pk,
                "SignatureValue": signature,
            },
        ))

        self.assertEqual(response.status_code, 400)
        order.refresh_from_db()
        payment.refresh_from_db()
        self.assertEqual(order.payment_status, "pending")
        self.assertEqual(payment.status, "pending")


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
