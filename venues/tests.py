from django.test import TestCase
from django.urls import reverse

from .forms import VenueAdditionRequestForm
from .models import VenueAdditionRequest


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
