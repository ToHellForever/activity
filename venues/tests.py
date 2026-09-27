from django.test import TestCase
from django.urls import reverse
from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model
from django.test import RequestFactory
from django.core.files.uploadedfile import SimpleUploadedFile

from .forms import VenueAdditionRequestForm
from .models import Venue, VenueAdditionRequest, VenueImage, VenueType, VenueView
from .admin import VenueAdmin
from .forms import VenueForm


class VenueAdditionRequestTests(TestCase):
	def valid_data(self):
		return {
			"venue_name": "Конференц-зал",
			"address": "ул. Тестовая, 1",
			"applicant_name": "Иван Петров",
			"applicant_phone": "+79996052164",
			"applicant_email": "ivan@example.com",
			"comment": "Площадка для деловых мероприятий",
		}

	def test_form_accepts_valid_data_and_normalizes_phone(self):
		form = VenueAdditionRequestForm(data=self.valid_data())

		self.assertTrue(form.is_valid())
		self.assertEqual(form.cleaned_data["applicant_phone"], "+79996052164")

	def test_form_rejects_invalid_email_and_phone(self):
		data = self.valid_data()
		data.update({"applicant_email": "invalid", "applicant_phone": "123"})

		form = VenueAdditionRequestForm(data=data)

		self.assertFalse(form.is_valid())
		self.assertIn("applicant_email", form.errors)
		self.assertIn("applicant_phone", form.errors)

	def test_public_request_creates_pending_application(self):
		response = self.client.post(
			reverse("venues:venue_addition_request"),
			self.valid_data(),
		)

		self.assertEqual(response.status_code, 200)
		self.assertJSONEqual(response.content, {"success": True})
		self.assertEqual(VenueAdditionRequest.objects.count(), 1)
		self.assertEqual(VenueAdditionRequest.objects.get().status, "new")


class VenueAdminCrudTests(TestCase):
	def test_uploaded_image_is_created_after_venue_is_saved(self):
		venue_type = VenueType.objects.create(name="Конференц-зал")
		form = VenueForm(data={
			"tariff": 1,
			"title": "Тестовая площадка",
			"description": "Описание",
			"venue_type": venue_type.pk,
			"address": "ул. Тестовая, 1",
			"city": "Новосибирск",
			"district": "",
			"metro": "",
			"area": 100,
			"max_capacity": 50,
			"price": 1000,
			"price_unit": "day",
			"equipment": [],
			"formats": [],
			"status": "draft",
			"contacts_opened": False,
			"contact_info": "",
			"email": "venue@example.com",
			"meta_title": "",
			"meta_description": "",
		}, files={
			"images": [SimpleUploadedFile("venue.jpg", b"image")],
		})
		self.assertTrue(form.is_valid(), form.errors)

		request = RequestFactory().post("/admin/venues/venue/add/")
		request.FILES.setlist("images", [SimpleUploadedFile("venue.jpg", b"image")])
		admin_obj = VenueAdmin(Venue, AdminSite())
		venue = admin_obj.save_form(request, form, change=False)

		self.assertIsNone(venue.pk)
		self.assertEqual(VenueImage.objects.count(), 0)
		venue.save()
		admin_obj.save_related(request, form, [], change=False)

		self.assertEqual(VenueImage.objects.filter(venue=venue).count(), 1)


class VenueViewTrackingTests(TestCase):
	"""Фиксация переходов на страницы площадок и отчёт в админке."""

	def setUp(self):
		self.venue_type = VenueType.objects.create(name="Конференц-зал")
		self.venue = Venue.objects.create(
			title="Тестовая площадка",
			slug="test-venue",
			venue_type=self.venue_type,
			address="ул. Тестовая, 1",
			city="Новосибирск",
			area=100,
			max_capacity=50,
			price=1000,
			status="published",
		)
		self.admin = get_user_model().objects.create_superuser(
			username="admin", email="admin@example.com", password="admin"
		)

	def _open_venue(self, referer="", utm=""):
		url = reverse("venues:venue_detail", args=[self.venue.slug])
		if utm:
			url += f"?utm_source={utm}"
		extra = {"HTTP_REFERER": referer} if referer else {}
		return self.client.get(url, **extra)

	def test_view_is_recorded_with_source(self):
		"""Каждое открытие страницы площадки фиксируется с источником."""
		# Прямой переход с referer
		self._open_venue(referer="https://google.com/search?q=зал")
		# Переход с UTM-меткой
		self._open_venue(utm="yandex_direct")

		self.assertEqual(VenueView.objects.count(), 2)
		first, second = VenueView.objects.order_by("id")
		self.assertEqual(first.source, "google.com")
		self.assertEqual(second.source, "yandex_direct")
		self.assertEqual(first.venue, self.venue)

	def test_anonymous_views_have_session_key(self):
		"""Анонимные посетители фиксируются по ключу сессии."""
		self._open_venue()
		view = VenueView.objects.get()
		self.assertIsNone(view.user)
		self.assertTrue(view.session_key)

	def test_admin_report_page_shows_stats(self):
		"""Отчёт в админке показывает переходы за период."""
		for _ in range(3):
			self._open_venue()

		self.client.force_login(self.admin)
		response = self.client.get(
			f"/admin/venues/venue/{self.venue.id}/views/"
		)

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, "Тестовая площадка")
		self.assertContains(response, "Всего переходов")

	def test_admin_report_respects_period_filter(self):
		"""Фильтр по периоду учитывает только переходы внутри него."""
		self._open_venue()

		self.client.force_login(self.admin)
		# Период в будущем — переходы не попадают
		response = self.client.get(
			f"/admin/venues/venue/{self.venue.id}/views/",
			{"period_start": "01.01.2050", "period_end": "31.01.2050"},
		)

		self.assertEqual(response.status_code, 200)
		# В контексте 0 переходов за выбранный период
		self.assertEqual(response.context["total_views"], 0)
