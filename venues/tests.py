from django.test import TestCase
from django.urls import reverse
from django.contrib.admin.sites import AdminSite
from django.test import RequestFactory
from django.core.files.uploadedfile import SimpleUploadedFile

from .forms import VenueAdditionRequestForm
from .models import Venue, VenueAdditionRequest, VenueImage, VenueType
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
