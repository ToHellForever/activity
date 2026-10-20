from datetime import timedelta
from tempfile import TemporaryDirectory

from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from core.admin import FAQCategoryAdmin, PartnerAgreementAdmin
from core.models import (
    FAQCategory,
    FAQItem,
    MarketingConsentEvent,
    PartnerAgreement,
)


User = get_user_model()


class FAQDisplayTests(TestCase):
    def test_existing_faq_categories_are_seeded(self):
        self.assertTrue(
            FAQCategory.objects.filter(name="Вопросы для участников").exists()
        )
        self.assertTrue(
            FAQItem.objects.filter(
                question="Как купить билет?",
                category__name="Вопросы для участников",
            ).exists()
        )

    def test_public_faq_shows_active_items_and_hides_inactive_items(self):
        category = FAQCategory.objects.create(name="Категория для теста")
        FAQItem.objects.create(
            category=category,
            question="Активный вопрос для теста",
            answer="Ответ на активный вопрос.",
        )
        FAQItem.objects.create(
            category=category,
            question="Неактивный вопрос для теста",
            answer="Ответ на неактивный вопрос.",
            is_active=False,
        )

        response = self.client.get(reverse("faq"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Категория для теста")
        self.assertContains(response, "Активный вопрос для теста")
        self.assertNotContains(response, "Неактивный вопрос для теста")


class FAQCategoryIconTests(TestCase):
    def setUp(self):
        self.media_directory = TemporaryDirectory()
        self.settings_override = override_settings(
            MEDIA_ROOT=self.media_directory.name,
            USE_YANDEX_CLOUD=False,
        )
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)
        self.addCleanup(self.media_directory.cleanup)

    def _icon(self, name, contents=b"<svg></svg>"):
        return SimpleUploadedFile(name, contents, content_type="image/svg+xml")

    def test_uploaded_icon_is_rendered_on_faq_page(self):
        category = FAQCategory.objects.create(
            name="Категория с загруженной иконкой",
            icon=self._icon("category-icon.svg"),
        )
        FAQItem.objects.create(
            category=category,
            question="Вопрос с иконкой",
            answer="Ответ.",
        )

        response = self.client.get(reverse("faq"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, category.icon.url)
        self.assertContains(response, "Категория с загруженной иконкой")

    def test_replacing_and_deleting_category_removes_icon_files(self):
        category = FAQCategory.objects.create(
            name="Категория с заменой иконки",
            icon=self._icon("old-icon.svg"),
        )
        storage = category.icon.storage
        old_icon_name = category.icon.name

        category.icon = self._icon("new-icon.svg")
        category.save()

        self.assertFalse(storage.exists(old_icon_name))
        new_icon_name = category.icon.name
        self.assertTrue(storage.exists(new_icon_name))

        category.delete()

        self.assertFalse(storage.exists(new_icon_name))

    def test_admin_bulk_delete_removes_icon_files(self):
        category = FAQCategory.objects.create(
            name="Категория на удаление",
            icon=self._icon("bulk-delete-icon.svg"),
        )
        storage = category.icon.storage
        icon_name = category.icon.name
        model_admin = FAQCategoryAdmin(FAQCategory, AdminSite())

        model_admin.delete_queryset(
            RequestFactory().post("/admin/core/faqcategory/"),
            FAQCategory.objects.filter(pk=category.pk),
        )

        self.assertFalse(storage.exists(icon_name))


class PartnerAgreementStorageTests(TestCase):
    def setUp(self):
        self.media_directory = TemporaryDirectory()
        self.settings_override = override_settings(
            MEDIA_ROOT=self.media_directory.name,
            USE_YANDEX_CLOUD=False,
        )
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)
        self.addCleanup(self.media_directory.cleanup)

    def _upload(self, filename, contents):
        return SimpleUploadedFile(filename, contents)

    def test_replacement_and_deletion_remove_files_from_storage(self):
        agreement = PartnerAgreement()
        agreement.file = self._upload("first.pdf", b"first contract")
        agreement.save()
        storage = agreement.file.storage
        old_file_name = agreement.file.name
        self.assertTrue(storage.exists(old_file_name))

        agreement.file = self._upload("replacement.docx", b"replacement contract")
        agreement.save()

        self.assertFalse(storage.exists(old_file_name))
        replacement_name = agreement.file.name
        self.assertTrue(storage.exists(replacement_name))

        agreement.delete()

        self.assertFalse(storage.exists(replacement_name))
        self.assertFalse(PartnerAgreement.objects.filter(pk=agreement.pk).exists())

    def test_saving_other_fields_does_not_remove_the_current_file(self):
        agreement = PartnerAgreement.objects.create(
            file=self._upload("current.pdf", b"current contract"),
        )
        storage = agreement.file.storage
        current_name = agreement.file.name
        agreement.file = self._upload("not-saved.pdf", b"not saved")
        agreement.is_active = False

        agreement.save(update_fields=["is_active"])
        agreement.refresh_from_db()

        self.assertEqual(agreement.file.name, current_name)
        self.assertTrue(storage.exists(current_name))

    def test_admin_bulk_delete_removes_files_from_storage(self):
        agreement = PartnerAgreement.objects.create(
            file=self._upload("bulk-delete.pdf", b"contract to delete"),
        )
        storage = agreement.file.storage
        file_name = agreement.file.name
        model_admin = PartnerAgreementAdmin(PartnerAgreement, AdminSite())

        model_admin.delete_queryset(
            RequestFactory().post("/admin/core/partneragreement/"),
            PartnerAgreement.objects.filter(pk=agreement.pk),
        )

        self.assertFalse(storage.exists(file_name))
        self.assertFalse(PartnerAgreement.objects.filter(pk=agreement.pk).exists())

    def test_download_uses_the_uploaded_file_name_and_contents(self):
        agreement = PartnerAgreement.objects.create(
            file=self._upload("partner-contract.pdf", b"contract contents"),
        )

        response = self.client.get(reverse("organizer_contract_download"))

        self.assertEqual(response.status_code, 200)
        self.assertIn("partner-contract.pdf", response["Content-Disposition"])
        self.assertEqual(b"".join(response.streaming_content), b"contract contents")


class ExistingAgreementSeedTests(TestCase):
    def test_existing_agreement_is_imported_and_readable(self):
        agreement = PartnerAgreement.objects.get(is_active=True)

        with agreement.file.open("rb") as uploaded_contract:
            self.assertTrue(uploaded_contract.read(4))


class PartnerMarketingConsentTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="partner-consent-test",
            email="partner-consent-test@example.com",
            password="test-password",
            user_type="partner",
        )
        self.client.force_login(self.user)
        self.url = reverse("partner:dashboard")

    def test_consent_is_saved_on_change_and_unchanged_posts_do_not_change_date(self):
        response = self.client.post(
            self.url,
            {"save_consent": "1", "consent_marketing": "on"},
        )
        self.assertEqual(response.status_code, 302)
        self.user.refresh_from_db()
        self.assertTrue(self.user.consent_marketing)
        first_change_at = self.user.consent_marketing_at
        self.assertEqual(
            MarketingConsentEvent.objects.filter(user=self.user).count(),
            1,
        )

        self.client.post(
            self.url,
            {"save_consent": "1", "consent_marketing": "on"},
        )
        self.user.refresh_from_db()
        self.assertEqual(self.user.consent_marketing_at, first_change_at)
        self.assertEqual(
            MarketingConsentEvent.objects.filter(user=self.user).count(),
            1,
        )

        previous_change_at = timezone.now() - timedelta(seconds=2)
        User.objects.filter(pk=self.user.pk).update(
            consent_marketing_at=previous_change_at,
        )
        self.client.post(self.url, {"save_consent": "1"})
        self.user.refresh_from_db()

        self.assertFalse(self.user.consent_marketing)
        self.assertGreater(self.user.consent_marketing_at, previous_change_at)
        self.assertEqual(
            list(
                MarketingConsentEvent.objects.filter(user=self.user)
                .order_by("changed_at")
                .values_list("consent", flat=True)
            ),
            [True, False],
        )

    def test_refusal_uses_error_toast(self):
        self.user.consent_marketing = True
        self.user.consent_marketing_at = timezone.now()
        self.user.save(update_fields=["consent_marketing", "consent_marketing_at"])

        self.client.post(self.url, {"save_consent": "1"})
        response = self.client.get(self.url)

        self.assertContains(response, "bg-danger")
        self.assertContains(response, "Вы отказались от рассылок.")
        self.assertContains(response, 'onchange="this.form.requestSubmit()"')
        self.assertNotContains(response, "Сохранить согласие")

    def test_admin_consent_list_filters_users_and_shows_status_and_date(self):
        consent_date = timezone.now() - timedelta(minutes=1)
        self.user.set_marketing_consent(True, changed_at=consent_date)
        self.user.set_marketing_consent(False)

        admin_user = User.objects.create_superuser(
            username="consent-admin",
            email="consent-admin@example.com",
            password="test-password",
        )
        self.client.force_login(admin_user)
        response = self.client.get(
            reverse("admin:core_marketingconsentevent_changelist")
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Просмотреть историю согласий на рассылку")
        self.assertContains(response, self.user.email)
        self.assertContains(response, "Согласен")
        self.assertContains(response, "Не согласен")
        self.assertContains(response, consent_date.strftime("%Y"))
        self.assertNotContains(
            response,
            reverse(
                "admin:core_marketingconsentevent_change",
                args=[MarketingConsentEvent.objects.first().pk],
            ),
        )
