from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from core.models import Event, Order, Ticket


class VisitorOrderPaginationTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.visitor = user_model.objects.create_user(
            username="pagination-visitor",
            email="pagination-visitor@example.com",
            password="test-password",
            user_type="visitor",
        )
        self.partner = user_model.objects.create_user(
            username="pagination-event-partner",
            email="pagination-event-partner@example.com",
            password="test-password",
            user_type="partner",
        )
        self.client.force_login(self.visitor)

    def _create_order(self, title, date_time):
        event = Event.objects.create(
            organizer=self.partner,
            title=title,
            description="Тестовое мероприятие",
            date_time=date_time,
            status="on_moderation",
        )
        ticket = Ticket.objects.create(
            event=event,
            name="Бесплатный тестовый билет",
            price=0,
            available_quantity=1,
            ticket_description="Тест",
        )
        order = Order.objects.create(
            ticket=ticket,
            participant_data={"email": self.visitor.email},
            total_price=0,
            payment_status="succeeded",
            is_paid=True,
            purchase_type="free_registration",
        )

    def test_dashboard_paginates_active_tickets(self):
        for index in range(13):
            self._create_order(
                f"Предстоящее событие {index}",
                timezone.now() + timedelta(days=index + 1),
            )

        url = reverse("visitor:dashboard")
        first_page = self.client.get(url)
        second_page = self.client.get(url, {"page": 2})

        self.assertEqual(first_page.status_code, 200)
        self.assertEqual(len(first_page.context["ticket_items"]), 12)
        self.assertEqual(first_page.content.count(b'class="card ticket-card"'), 12)
        self.assertContains(first_page, 'class="visitor-pagination-bar"')
        self.assertContains(first_page, "visitor-pagination-link")
        self.assertContains(first_page, "page=2")
        self.assertEqual(second_page.status_code, 200)
        self.assertEqual(second_page.content.count(b'class="card ticket-card"'), 1)

    def test_order_history_paginates_past_tickets(self):
        for index in range(13):
            self._create_order(
                f"Прошедшее событие {index}",
                timezone.now() - timedelta(days=index + 1),
            )

        url = reverse("visitor:order_history")
        first_page = self.client.get(url)
        second_page = self.client.get(url, {"page": 2})

        self.assertEqual(first_page.status_code, 200)
        self.assertEqual(len(first_page.context["past_ticket_items"]), 12)
        self.assertEqual(first_page.content.count(b'class="card ticket-card"'), 12)
        self.assertContains(first_page, 'class="visitor-pagination-bar"')
        self.assertContains(first_page, "visitor-pagination-link")
        self.assertContains(first_page, "page=2")
        self.assertEqual(second_page.status_code, 200)
        self.assertEqual(second_page.content.count(b'class="card ticket-card"'), 1)
