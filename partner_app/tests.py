from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from core.models import Event, Order, Ticket


class PartnerListPaginationTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.partner = user_model.objects.create_user(
            username="pagination-partner",
            email="pagination-partner@example.com",
            password="test-password",
            user_type="partner",
        )
        self.client.force_login(self.partner)

    def _create_event(self, title, date_time):
        return Event.objects.create(
            organizer=self.partner,
            title=title,
            description="Тестовое мероприятие",
            date_time=date_time,
            status="on_moderation",
        )

    def test_partner_event_list_paginates_active_and_archived_events(self):
        now = timezone.now()
        for index in range(13):
            self._create_event(
                f"Будущее мероприятие {index}",
                now + timedelta(days=index + 1),
            )
            self._create_event(
                f"Прошедшее мероприятие {index}",
                now - timedelta(days=index + 1),
            )

        response = self.client.get(reverse("partner:partner_event_list"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.count(b'class="card partner-event-card"'), 18)
        self.assertContains(response, "page_size=9")
        self.assertContains(response, "active_page=2")
        self.assertContains(response, "archived_page=2")

        second_page = self.client.get(
            reverse("partner:partner_event_list"),
            {"page_size": 9, "active_page": 2, "archived_page": 2},
        )

        self.assertEqual(second_page.status_code, 200)
        self.assertEqual(second_page.content.count(b'class="card partner-event-card"'), 8)

        mobile_first_page = self.client.get(
            reverse("partner:partner_event_list"),
            {"page_size": 8},
        )
        self.assertEqual(mobile_first_page.status_code, 200)
        self.assertEqual(
            mobile_first_page.content.count(b'class="card partner-event-card"'),
            16,
        )

        mobile_second_page = self.client.get(
            reverse("partner:partner_event_list"),
            {"page_size": 8, "active_page": 2, "archived_page": 2},
        )
        self.assertEqual(mobile_second_page.status_code, 200)
        self.assertEqual(
            mobile_second_page.content.count(b'class="card partner-event-card"'),
            10,
        )

    def test_participant_list_paginates_orders(self):
        event = self._create_event(
            "Участники тестирования",
            timezone.now() + timedelta(days=2),
        )
        ticket = Ticket.objects.create(
            event=event,
            name="Бесплатный тестовый билет",
            price=0,
            available_quantity=200,
            ticket_description="Тест",
        )
        for index in range(26):
            Order.objects.create(
                ticket=ticket,
                participant_data={
                    "first_name": f"Участник {index}",
                    "email": f"participant-{index}@example.com",
                },
                total_price=0,
                payment_status="succeeded",
                is_paid=True,
                purchase_type="free_registration",
            )

        url = reverse("partner:participant_list", args=[event.pk])
        first_page = self.client.get(url)
        second_page = self.client.get(url, {"page": 2})

        self.assertEqual(first_page.status_code, 200)
        self.assertEqual(first_page.content.count(b'class="card order-card mb-3"'), 25)
        self.assertContains(first_page, "page=2")
        self.assertEqual(second_page.status_code, 200)
        self.assertEqual(second_page.content.count(b'class="card order-card mb-3"'), 1)
