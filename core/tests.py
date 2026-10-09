"""
Тесты для функционала водяных знаков.
"""

import os
import re
import tempfile
from datetime import timedelta

from django.core import mail
from django.test import SimpleTestCase, TestCase, override_settings
from django.contrib.admin.sites import AdminSite
from django.test import RequestFactory
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.exceptions import ValidationError
from django.utils import timezone
from PIL import Image, ImageDraw
from core.utils import add_watermark_to_image, add_watermark_to_video
from core.models import (
    Event,
    CustomUser,
    User,
    EventPackage,
    UserPackageSubscription,
    PartnerDocument,
    PayoutDetails,
    PayoutRequest,
    EmailVerificationCode,
)
from core.admin import (
    EventAdmin,
    PartnerDocumentAdmin,
    PayoutRequestAdmin,
    UserPackageSubscriptionAdmin,
)
from core.tasks import check_and_apply_scheduled_package_changes
from core.forms import EventAdminForm
from core.validators import validate_inn, validate_video_duration
from core.templatetags.format_filters import auto_format
from core.video_storage import YandexVideoProcessingStorage
from unittest.mock import patch, MagicMock


class InnValidatorTestCase(SimpleTestCase):
    def test_accepts_ten_or_twelve_digits_without_checksum_validation(self):
        self.assertEqual(validate_inn("1234567890"), "1234567890")
        self.assertEqual(validate_inn("123456789012"), "123456789012")

    def test_rejects_other_lengths_and_non_digits(self):
        for value in ("123456789", "12345678901", "1234567890123", "123456789a"):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                validate_inn(value)


class EventDescriptionFormattingTestCase(SimpleTestCase):
    def test_admin_description_field_explains_simple_formatting(self):
        description = EventAdminForm().fields["description"]

        self.assertIn("**жирный**", description.help_text)
        self.assertEqual(description.widget.attrs["rows"], 10)
        self.assertIn("https://example.com", description.widget.attrs["placeholder"])

    def test_plain_url_becomes_safe_active_link(self):
        rendered = str(auto_format("Подробнее: https://example.com/event."))

        self.assertIn(
            '<a href="https://example.com/event" target="_blank" rel="noopener noreferrer">'
            "https://example.com/event</a>.",
            rendered,
        )

    def test_formatted_text_and_markdown_link_render(self):
        rendered = str(
            auto_format("**Важно**\n\n[Открыть сайт](https://example.com)")
        )

        self.assertIn("<b>Важно</b>", rendered)
        self.assertIn(
            '<a href="https://example.com" target="_blank" rel="noopener noreferrer">'
            "Открыть сайт</a>",
            rendered,
        )

    def test_list_is_followed_by_a_new_paragraph_without_a_break(self):
        rendered = str(auto_format("Перед списком\n- Пункт списка\nПосле списка"))

        self.assertIn(
            "<p>Перед списком</p><ul><li>Пункт списка</li></ul>"
            "<p>После списка</p>",
            rendered,
        )
        self.assertNotIn("</ul><br>", rendered)

    def test_unsafe_markup_and_non_http_links_are_not_rendered(self):
        rendered = str(
            auto_format('<script>alert(1)</script> [опасно](javascript:alert(1))')
        )

        self.assertNotIn("<script>", rendered)
        self.assertNotIn("<a ", rendered)

    def test_paragraph_font_size_markers_render_as_limited_inline_styles(self):
        rendered = str(
            auto_format("[[size=13]]Обычный абзац[[/size]]\n[[size=20]]Крупный абзац[[/size]]")
        )

        self.assertIn('<span style="font-size:13px">Обычный абзац</span>', rendered)
        self.assertIn('<span style="font-size:20px">Крупный абзац</span>', rendered)

    def test_unsupported_paragraph_font_size_marker_is_escaped(self):
        rendered = str(auto_format("[[size=99]]Текст[[/size]]"))

        self.assertNotIn('<span style=', rendered)
        self.assertIn("[[size=99]]Текст[[/size]]", rendered)

    def test_internal_size_markers_do_not_use_description_character_limit(self):
        from core.description_utils import (
            description_character_count,
            strip_description_size_markers,
        )

        description = (
            "[[size=13]]Первый абзац[[/size]]\n"
            "[[size=20]]Второй абзац[[/size]]"
        )
        self.assertEqual(
            description_character_count(description),
            len("Первый абзац\nВторой абзац"),
        )
        self.assertEqual(
            strip_description_size_markers(description),
            "Первый абзац\nВторой абзац",
        )


class VerifiedOrganizerStatusTestCase(SimpleTestCase):
    def test_email_verification_alone_does_not_verify_an_organizer(self):
        user = CustomUser(
            user_type="visitor",
            is_verified=True,
            organizer_status="none",
        )

        self.assertFalse(user.is_verified_organizer)

    def test_only_approved_partner_is_a_verified_organizer(self):
        approved_partner = CustomUser(
            user_type="partner",
            organizer_status="approved",
        )
        pending_partner = CustomUser(
            user_type="partner",
            organizer_status="pending",
        )

        self.assertTrue(approved_partner.is_verified_organizer)
        self.assertFalse(pending_partner.is_verified_organizer)


class YandexVideoStorageTestCase(SimpleTestCase):
    """Тесты для удаления видео из Yandex-backed хранилища."""

    @override_settings(USE_YANDEX_CLOUD=True)
    def test_delete_removes_remote_file_from_cloud_storage(self):
        storage = YandexVideoProcessingStorage(subdirectory="partner_video")
        storage.cloud_storage = MagicMock()

        with patch("os.path.exists", return_value=True), patch("os.remove") as remove_mock:
            storage.delete("partner_video/test.mp4")

        storage.cloud_storage.delete.assert_called_once_with("partner_video/test.mp4")
        remove_mock.assert_called_once()


class WatermarkTestCase(TestCase):
    """Тесты для добавления водяных знаков."""

    def setUp(self):
        """Создаем тестовые данные."""
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
            user_type="partner",
        )

        # Создаем временный логотип для водяного знака
        self.watermark_path = tempfile.mktemp(suffix=".png")
        self._create_test_watermark()

    def _create_test_watermark(self):
        """Создает тестовый водяной знак."""
        img = Image.new("RGBA", (100, 50), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        draw.text((10, 10), "Test Logo", fill=(255, 255, 255, 128))
        img.save(self.watermark_path)

    def test_add_watermark_to_image(self):
        """Тест добавления водяного знака на изображение."""
        # Создаем тестовое изображение
        test_image_path = tempfile.mktemp(suffix=".png")
        img = Image.new("RGB", (400, 400), color="red")
        img.save(test_image_path)

        # Добавляем водяной знак
        result = add_watermark_to_image(
            test_image_path, self.watermark_path, test_image_path
        )

        self.assertTrue(result)
        self.assertTrue(os.path.exists(test_image_path))

        # Проверяем, что размер файла изменился
        original_size = os.path.getsize(test_image_path)
        self.assertGreater(original_size, 0)

    def test_add_watermark_to_video(self):
        """Тест добавления водяного знака на видео."""
        # Создаем тестовое видео (заглушка)
        test_video_path = tempfile.mktemp(suffix=".mp4")
        with open(test_video_path, "wb") as f:
            f.write(os.urandom(1024 * 1024))  # 1MB заглушка

        # Пробуем добавить водяной знак
        result = add_watermark_to_video(
            test_video_path, self.watermark_path, test_video_path
        )

        # Ожидаем False, так как это не настоящее видео
        self.assertFalse(result)

    def test_event_watermark_on_save(self):
        """Тест добавления водяного знака при сохранении события."""
        # Создаем тестовое изображение
        test_image_path = tempfile.mktemp(suffix=".png")
        img = Image.new("RGB", (400, 400), color="blue")
        img.save(test_image_path)

        # Создаем событие с изображением
        with open(test_image_path, "rb") as f:
            event_image = SimpleUploadedFile(
                "test_image.png", f.read(), content_type="image/png"
            )

        event = Event(
            title="Test Event",
            description="description",
            date_time="2026-12-31T23:59:59Z",
            place_data={"address": "Test Place"},
            organizer=self.user,
            image=event_image,
        )
        event.save()

        # Проверяем, что изображение сохранено
        self.assertTrue(event.image)
        # Storage может не поддерживать абсолютные пути (облачное хранилище),
        # поэтому проверяем существование через API хранилища
        self.assertTrue(event.image.storage.exists(event.image.name))

    def tearDown(self):
        """Удаляем временные файлы."""
        if os.path.exists(self.watermark_path):
            os.remove(self.watermark_path)

    def test_validate_video_duration(self):
        """Тест валидации длительности видео."""

        class FakeVideoFile:
            """Заглушка загруженного файла: только .path, без авто-атрибутов."""

            def __init__(self, path):
                self.path = path

        # Создаем временный файл
        test_video_path = tempfile.mktemp(suffix=".mp4")
        with open(test_video_path, "wb") as f:
            f.write(os.urandom(1024 * 1024))  # 1MB заглушка

        mock_file = FakeVideoFile(test_video_path)

        # Мок для VideoFileClip: патчим ссылку в модуле валидатора,
        # а не в moviepy (core.validators импортировал её при загрузке)
        mock_video_clip = MagicMock()
        mock_video_clip.__enter__.return_value = mock_video_clip
        mock_video_clip.duration = 320  # дольше порога валидатора (310 сек)

        # Проверяем, что валидатор выдает ошибку для видео длиннее 5 минут
        with patch("core.validators.VideoFileClip", return_value=mock_video_clip):
            with self.assertRaises(ValidationError):
                validate_video_duration(mock_file)

        # Проверяем, что валидатор не выдает ошибку для видео короче 5 минут
        mock_video_clip.duration = 299  # 4 минуты и 59 секунд
        with patch("core.validators.VideoFileClip", return_value=mock_video_clip):
            try:
                validate_video_duration(mock_file)
            except ValidationError:
                self.fail("validate_video_duration raised ValidationError unexpectedly!")

        # Удаляем временный файл
        if os.path.exists(test_video_path):
            os.remove(test_video_path)


class PackageSubscriptionLifecycleTestCase(TestCase):
    """
    Тесты жизненного цикла подписок на пакеты:
    истечение срока и запланированная смена пакета.
    """

    def setUp(self):
        self.user = User.objects.create_user(
            username="subuser",
            email="subuser@example.com",
            password="testpass123",
            user_type="partner",
        )
        self.basic_package = EventPackage.objects.create(
            name="Старт",
            price=100,
            event_card_type="basic",
            max_photos=3,
        )
        self.priority_package = EventPackage.objects.create(
            name="Приоритет",
            price=300,
            event_card_type="priority",
            max_photos=10,
        )

    def _create_subscription(self, *, end_date, is_active=True):
        """Создаёт подписку с заданной датой окончания."""
        subscription = UserPackageSubscription(
            user=self.user,
            package=self.basic_package,
            subscription_type="monthly",
            is_active=is_active,
        )
        # save() пересчитывает end_date только для новых подписок,
        # поэтому задаём дату после первого сохранения
        subscription.save()
        subscription.end_date = end_date
        subscription.save(update_fields=["end_date"])
        subscription.refresh_from_db()
        return subscription

    def test_expired_subscription_deactivated_by_task(self):
        """Истёкшая подписка деактивируется задачей."""
        subscription = self._create_subscription(
            end_date=timezone.now() - timedelta(days=1)
        )
        self.assertTrue(subscription.is_active)  # в БД ещё активна

        check_and_apply_scheduled_package_changes()

        subscription.refresh_from_db()
        self.assertFalse(subscription.is_active)

    def test_active_subscription_not_touched_by_task(self):
        """Действующая подписка задачей не трогается."""
        subscription = self._create_subscription(
            end_date=timezone.now() + timedelta(days=10)
        )

        check_and_apply_scheduled_package_changes()

        subscription.refresh_from_db()
        self.assertTrue(subscription.is_active)

    def test_scheduled_change_applies_after_expiry(self):
        """Запланированная смена применяется после окончания текущей подписки."""
        subscription = self._create_subscription(
            end_date=timezone.now() - timedelta(hours=1)
        )
        subscription.schedule_package_change(self.priority_package)
        subscription.refresh_from_db()
        self.assertEqual(subscription.scheduled_change_to, self.priority_package)

        check_and_apply_scheduled_package_changes()

        subscription.refresh_from_db()
        # Старая подписка закрыта
        self.assertFalse(subscription.is_active)
        self.assertIsNone(subscription.scheduled_change_to)

        # Создана новая активная подписка на новый пакет
        new_subscription = UserPackageSubscription.objects.filter(
            user=self.user, package=self.priority_package, is_active=True
        ).first()
        self.assertIsNotNone(new_subscription)
        self.assertGreater(new_subscription.end_date, timezone.now())

        # Активная подписка у пользователя ровно одна — на новый пакет
        active_subscriptions = UserPackageSubscription.objects.filter(
            user=self.user, is_active=True
        )
        self.assertEqual(active_subscriptions.count(), 1)
        self.assertEqual(active_subscriptions.first().pk, new_subscription.pk)

    def test_scheduled_change_not_applied_before_expiry(self):
        """До окончания текущей подписки смена не применяется."""
        subscription = self._create_subscription(
            end_date=timezone.now() + timedelta(days=5)
        )
        subscription.schedule_package_change(self.priority_package)

        check_and_apply_scheduled_package_changes()

        subscription.refresh_from_db()
        self.assertTrue(subscription.is_active)
        self.assertEqual(subscription.scheduled_change_to, self.priority_package)
        self.assertFalse(
            UserPackageSubscription.objects.filter(
                user=self.user, package=self.priority_package, is_active=True
            ).exists()
        )

    def test_expired_without_scheduled_change_leaves_no_active_subscription(self):
        """После истечения подписки без запланированной смены активных нет."""
        self._create_subscription(
            end_date=timezone.now() - timedelta(days=1)
        )

        check_and_apply_scheduled_package_changes()

        self.assertFalse(
            UserPackageSubscription.objects.filter(
                user=self.user, is_active=True
            ).exists()
        )

    def test_explicit_end_date_is_preserved_on_creation(self):
        """Явный срок подписки не заменяется автоматическим месячным сроком."""
        end_date = timezone.now() + timedelta(days=90)
        subscription = UserPackageSubscription.objects.create(
            user=self.user,
            package=self.basic_package,
            subscription_type="monthly",
            end_date=end_date,
        )

        subscription.refresh_from_db()
        self.assertAlmostEqual(
            subscription.end_date.timestamp(),
            end_date.timestamp(),
            delta=1,
        )


class AdminCrudRegressionTestCase(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.site = AdminSite()
        self.admin_user = User.objects.create_superuser(
            username="admin",
            email="admin@example.com",
            password="adminpass123",
        )
        self.partner = User.objects.create_user(
            username="partner-admin-test",
            email="partner-admin-test@example.com",
            password="testpass123",
            user_type="partner",
        )
        self.package_basic = EventPackage.objects.create(name="Admin Basic", price=100)
        self.package_priority = EventPackage.objects.create(name="Admin Priority", price=300)

    def test_document_rejection_updates_partner_status(self):
        document = PartnerDocument.objects.create(
            user=self.partner,
            document=SimpleUploadedFile("document.pdf", b"pdf"),
        )
        document.is_approved = False
        document.rejection_reason = "Нужен читаемый документ"

        request = self.factory.post("/admin/core/partnerdocument/")
        request.user = self.admin_user
        PartnerDocumentAdmin(PartnerDocument, self.site).save_model(
            request, document, form=None, change=True
        )

        self.partner.refresh_from_db()
        document.refresh_from_db()
        self.assertEqual(self.partner.organizer_status, "rejected")
        self.assertEqual(self.partner.organizer_rejection_reason, "Нужен читаемый документ")
        self.assertEqual(document.reviewer_id, self.admin_user.id)
        self.assertIsNotNone(document.reviewed_at)

    def test_bulk_subscription_activation_keeps_one_active_subscription_per_user(self):
        first = UserPackageSubscription.objects.create(
            user=self.partner,
            package=self.package_basic,
            is_active=False,
            subscription_type="monthly",
        )
        second = UserPackageSubscription.objects.create(
            user=self.partner,
            package=self.package_priority,
            is_active=False,
            subscription_type="monthly",
        )
        request = self.factory.post("/admin/core/userpackagesubscription/")
        request.user = self.admin_user
        admin_obj = UserPackageSubscriptionAdmin(UserPackageSubscription, self.site)

        with patch.object(admin_obj, "message_user"):
            admin_obj.activate_subscriptions(
                request,
                UserPackageSubscription.objects.filter(pk__in=[first.pk, second.pk]),
            )

        active = UserPackageSubscription.objects.filter(user=self.partner, is_active=True)
        self.assertEqual(active.count(), 1)
        self.assertEqual(active.first().pk, second.pk)

    def test_bulk_event_activation_respects_package_limit(self):
        active_event = Event.objects.create(
            organizer=self.partner,
            title="Уже активно",
            description="Описание",
            date_time=timezone.now() + timedelta(days=2),
            status="active",
            package=self.package_basic,
        )
        pending_event = Event.objects.create(
            organizer=self.partner,
            title="Ожидает",
            description="Описание",
            date_time=timezone.now() + timedelta(days=3),
            status="on_moderation",
            package=self.package_basic,
        )
        request = self.factory.post("/admin/core/event/")
        request.user = self.admin_user
        admin_obj = EventAdmin(Event, self.site)

        with patch.object(admin_obj, "message_user"), self.assertRaises(ValidationError):
            admin_obj.to_active(request, Event.objects.filter(pk=pending_event.pk))

        pending_event.refresh_from_db()
        self.assertEqual(pending_event.status, "on_moderation")
        self.assertEqual(active_event.status, "active")

    def test_reject_payout_action_saves_admin_comment(self):
        details = PayoutDetails.objects.create(
            partner=self.partner,
            bank_name="other",
            account_number="123",
            account_holder="Иван Петров",
        )
        payout = PayoutRequest.objects.create(
            organizer=self.partner,
            amount=100,
            payment_details=details,
        )
        request = self.factory.post(
            "/admin/core/payoutrequest/",
            {
                "apply_rejection": "1",
                "rejection_comment": "Не хватает подтверждающих документов",
                "_selected_action": [str(payout.pk)],
            },
        )
        request.user = self.admin_user
        admin_obj = PayoutRequestAdmin(PayoutRequest, self.site)

        with patch.object(admin_obj, "message_user"):
            admin_obj.mark_as_rejected(request, PayoutRequest.objects.filter(pk=payout.pk))

        payout.refresh_from_db()
        self.assertEqual(payout.status, "rejected")
        self.assertEqual(payout.rejection_comment, "Не хватает подтверждающих документов")


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    DEFAULT_FROM_EMAIL="no-reply@example.com",
)
class ForgotPasswordTestCase(TestCase):
    URL = "/forgot-password/"

    def test_unknown_email_shows_error_without_sending_email(self):
        email = "unknown@example.com"

        response = self.client.post(self.URL, {"email": email})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Пользователь с таким адресом электронной почты не найден.")
        self.assertContains(response, f'value="{email}"')
        self.assertEqual(len(mail.outbox), 0)

    def test_existing_email_receives_reset_link(self):
        email = "known@example.com"
        user = User.objects.create_user(
            username=email,
            email=email,
            password="Str0ng!Pass2026",
        )

        response = self.client.post(self.URL, {"email": email})

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "registration/forgot_password_success.html")
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [email])
        user.refresh_from_db()
        self.assertTrue(user.password_reset_token)


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    DEFAULT_FROM_EMAIL="no-reply@example.com",
)
class RegistrationEmailCodeTestCase(TestCase):
    """
    Тесты логики регистрации с отправкой кода подтверждения на почту:
    создание пользователя, письмо с кодом, подтверждение кода, повторная отправка.
    """

    REGISTER_URL = "/register/"
    VERIFY_URL = "/verify-email/"
    RESEND_URL = "/resend-verification-code/"

    def _register_visitor(self, email="newvisitor@example.com", *, with_consent=True):
        """Выполняет POST-регистрацию посетителя и возвращает response."""
        data = {
            "form_type": "visitor",
            "email": email,
            "password1": "Str0ng!Pass2026",
            "password2": "Str0ng!Pass2026",
        }
        if with_consent:
            data["agree_personal_data"] = "on"
        return self.client.post(self.REGISTER_URL, data)

    def _extract_code_from_email(self, message):
        """Достаёт 5-значный код из HTML-альтернативы письма."""
        html = next(
            content for content, mimetype in message.alternatives
            if mimetype == "text/html"
        )
        match = re.search(r'class="code-value">(\d{5})<', html)
        self.assertIsNotNone(match, "Код не найден в HTML-письме")
        return match.group(1)

    def test_registration_creates_unverified_user_and_redirects(self):
        """Регистрация создаёт неподтверждённого пользователя и редиректит на ввод кода."""
        response = self._register_visitor()

        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, self.VERIFY_URL)

        user = User.objects.get(email="newvisitor@example.com")
        self.assertEqual(user.username, "newvisitor@example.com")
        self.assertEqual(user.user_type, "visitor")
        self.assertFalse(user.is_verified)
        self.assertEqual(
            self.client.session.get("unverified_user_id"), user.id
        )

    def test_registration_without_personal_data_consent_fails(self):
        """Без согласия на обработку ПД регистрация не проходит (152-ФЗ)."""
        response = self._register_visitor(with_consent=False)

        # Форма невалидна — пользователь не создан, редиректа нет
        self.assertEqual(response.status_code, 200)
        self.assertFalse(
            User.objects.filter(email="newvisitor@example.com").exists()
        )

    def test_registration_stores_consents(self):
        """Согласия сохраняются на пользователе вместе с датой."""
        self._register_visitor(email="consent@example.com")
        # Включим согласие на рассылку отдельным запросом
        self.client.post(
            self.REGISTER_URL,
            {
                "form_type": "visitor",
                "email": "consent2@example.com",
                "password1": "Str0ng!Pass2026",
                "password2": "Str0ng!Pass2026",
                "agree_personal_data": "on",
                "agree_marketing": "on",
            },
        )

        user = User.objects.get(email="consent2@example.com")
        self.assertTrue(user.consent_personal_data)
        self.assertIsNotNone(user.consent_personal_data_at)
        self.assertTrue(user.consent_marketing)
        self.assertIsNotNone(user.consent_marketing_at)


    def test_registration_sends_verification_code_email(self):
        """На почту уходит письмо с темой и кодом, совпадающим с кодом в БД."""
        self._register_visitor()

        # Ровно одно письмо
        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertEqual(message.subject, "Подтверждение почты")
        self.assertEqual(message.to, ["newvisitor@example.com"])

        # Код в письме совпадает с сохранённым в БД
        user = User.objects.get(email="newvisitor@example.com")
        db_code = EmailVerificationCode.objects.get(user=user, is_used=False).code
        email_code = self._extract_code_from_email(message)
        self.assertEqual(email_code, db_code)
        self.assertEqual(len(db_code), 5)
        self.assertTrue(db_code.isdigit())

    def test_verify_email_with_correct_code_verifies_and_logs_in(self):
        """Верный код подтверждает пользователя, помечает код и логинит его."""
        self._register_visitor()
        user = User.objects.get(email="newvisitor@example.com")
        code = EmailVerificationCode.objects.get(user=user, is_used=False).code

        response = self.client.post(
            self.VERIFY_URL,
            {
                "code1": code[0],
                "code2": code[1],
                "code3": code[2],
                "code4": code[3],
                "code5": code[4],
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, "/visitor/dashboard/", status_code=302)

        user.refresh_from_db()
        self.assertTrue(user.is_verified)
        self.assertTrue(
            EmailVerificationCode.objects.get(user=user).is_used
        )
        self.assertNotIn("unverified_user_id", self.client.session)
        self.assertEqual(self.client.session.get("_auth_user_id"), str(user.id))

    def test_verify_email_with_wrong_code_fails(self):
        """Неверный код не подтверждает пользователя и не логинит его."""
        self._register_visitor()
        user = User.objects.get(email="newvisitor@example.com")

        response = self.client.post(
            self.VERIFY_URL,
            {"code1": "0", "code2": "0", "code3": "0", "code4": "0", "code5": "0"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Неверный код подтверждения")

        user.refresh_from_db()
        self.assertFalse(user.is_verified)
        self.assertFalse(EmailVerificationCode.objects.get(user=user).is_used)

    def test_verify_email_without_session_redirects_to_login(self):
        """Без id неподтверждённого пользователя в сессии редирект на логин."""
        self.client.session.pop("unverified_user_id", None)

        response = self.client.get(self.VERIFY_URL)

        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, "/login/")

    def test_resend_invalidates_old_code_and_sends_new(self):
        """Повторная отправка помечает старый код использованным и создаёт новый."""
        self._register_visitor()
        user = User.objects.get(email="newvisitor@example.com")
        old_code = EmailVerificationCode.objects.get(user=user, is_used=False).code
        mail.outbox.clear()

        response = self.client.post(self.RESEND_URL)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json().get("success"), True)

        # Старый код помечен использованным
        self.assertTrue(
            EmailVerificationCode.objects.get(user=user, code=old_code).is_used
        )
        # Создан новый активный код
        new_active = EmailVerificationCode.objects.filter(
            user=user, is_used=False
        )
        self.assertEqual(new_active.count(), 1)
        self.assertNotEqual(new_active.first().code, old_code)

        # Ушло ровно одно новое письмо с новым кодом
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(
            self._extract_code_from_email(mail.outbox[0]), new_active.first().code
        )

    def test_resend_without_session_returns_400(self):
        """Повторная отправка без сессии возвращает 400."""
        self.client.session.pop("unverified_user_id", None)

        response = self.client.post(self.RESEND_URL)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json().get("success"), False)

    def test_partner_reregistration_overwrites_stale_visitor_account(self):
        """
        Регистрация партнёром на email незавершённой заявки посетителя.

        Поведение ролей должно быть одинаковым: если прежняя регистрация
        (пусть даже посетителем) не подтверждена кодом, партнёрская форма
        тоже молча перезаписывает её, а не пишет «email уже занят».
        """
        # Кто-то зарегистрировался посетителем на чужой email и не ввёл код.
        self._register_visitor(email="owner@example.com")
        visitor = User.objects.get(email="owner@example.com")
        self.assertFalse(visitor.is_verified)

        mail.outbox.clear()

        # Настоящий владелец регистрируется партнёром на тот же email.
        response = self.client.post(
            self.REGISTER_URL,
            {
                "form_type": "partner",
                "email": "owner@example.com",
                "password1": "Own3r!Pass2026",
                "password2": "Own3r!Pass2026",
                "company_name": "ООО Рога и копыта",
                "short_name": "Рога",
                "registration_type": "legal",
                "inn": "7707083893",
                "kpp": "770701001",
                "contact_person": "Иван Иванов",
                "phone": "+79990001122",
                "agree_terms": "on",
                "agree_user_agreement": "on",
                "agree_personal_data": "on",
            },
        )
        self.assertRedirects(response, self.VERIFY_URL)

        # Старый аккаунт посетителя удалён, создан партнёрский
        self.assertFalse(User.objects.filter(pk=visitor.pk).exists())
        partner = User.objects.get(email="owner@example.com")
        self.assertEqual(partner.user_type, "partner")
        self.assertFalse(partner.is_verified)

        # Письмо с новым кодом ушло
        self.assertEqual(len(mail.outbox), 1)


    def test_reregistration_overwrites_stale_unverified_account(self):
        """
        Повторная регистрация на email незавершённой заявки проходит как обычно.

        Владелец почты не должен видеть «email уже занят», если прежняя
        регистрация так и не подтверждена кодом: для него это выглядело бы
        как «аккаунт создали без меня». Старый неподтверждённый аккаунт
        стирается, письмо с новым кодом уходит на ящик.
        """
        # «Злоумышленник» зарегистрировался на чужой email и не ввёл код.
        first = self._register_visitor(email="owner@example.com")
        self.assertRedirects(first, self.VERIFY_URL)
        attacker = User.objects.get(email="owner@example.com")
        self.assertFalse(attacker.is_verified)

        # Настоящий владелец заходит на форму регистрации — и она работает.
        mail.outbox.clear()
        second = self.client.post(
            self.REGISTER_URL,
            {
                "form_type": "visitor",
                "email": "owner@example.com",
                "password1": "Own3r!Pass2026",
                "password2": "Own3r!Pass2026",
                "agree_personal_data": "on",
            },
        )
        self.assertRedirects(second, self.VERIFY_URL)


        # Старый аккаунт удалён, создан новый с паролем владельца
        self.assertFalse(User.objects.filter(pk=attacker.pk).exists())
        owner = User.objects.get(email="owner@example.com")
        self.assertNotEqual(owner.pk, attacker.pk)
        self.assertTrue(owner.check_password("Own3r!Pass2026"))
        self.assertFalse(owner.is_verified)

        # Письмо с кодом ушло ровно один раз
        self.assertEqual(len(mail.outbox), 1)

        # Код из письма подтверждается — владелец получает контроль
        code = EmailVerificationCode.objects.get(
            user=owner, is_used=False
        ).code
        verify_response = self.client.post(
            self.VERIFY_URL,
            {
                "code1": code[0],
                "code2": code[1],
                "code3": code[2],
                "code4": code[3],
                "code5": code[4],
            },
        )
        self.assertEqual(verify_response.status_code, 302)
        owner.refresh_from_db()
        self.assertTrue(owner.is_verified)

    def test_reregistration_keeps_verified_accounts_blocked(self):
        """Подтверждённый аккаунт остаётся занятым при повторной регистрации."""
        self._register_visitor(email="real@example.com")
        user = User.objects.get(email="real@example.com")
        code = EmailVerificationCode.objects.get(user=user, is_used=False).code
        self.client.post(
            self.VERIFY_URL,
            {
                "code1": code[0],
                "code2": code[1],
                "code3": code[2],
                "code4": code[3],
                "code5": code[4],
            },
        )
        user.refresh_from_db()
        self.assertTrue(user.is_verified)

        response = self.client.post(
            self.REGISTER_URL,
            {
                "form_type": "visitor",
                "email": "real@example.com",
                "password1": "Attack3r!Pass2026",
                "password2": "Attack3r!Pass2026",
                "agree_personal_data": "on",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "уже существует")
        user.refresh_from_db()
        self.assertTrue(user.check_password("Str0ng!Pass2026"))

    def test_resend_limit_is_three_per_registration(self):
        """После трёх отправок повторные запросы отклоняются (429)."""
        self._register_visitor()  # 1-я отправка при регистрации
        user = User.objects.get(email="newvisitor@example.com")

        # 2-я и 3-я — проходят
        for _ in range(2):
            response = self.client.post(self.RESEND_URL)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json().get("success"), True)

        # 4-я — отклоняется лимитом
        response = self.client.post(self.RESEND_URL)
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.json().get("success"), False)

        user.refresh_from_db()
        self.assertEqual(user.verification_send_count, 3)

    def test_stale_unverified_account_deleted_after_hour(self):
        """Незавершённая регистрация старше часа удаляется задачей."""
        from core.tasks import cleanup_stale_unverified_accounts

        self._register_visitor()
        user = User.objects.get(email="newvisitor@example.com")
        self.assertFalse(user.is_stale_unverified())

        # Симулируем, что последняя отправка была больше часа назад
        user.last_verification_sent_at = timezone.now() - timedelta(hours=2)
        user.save(update_fields=["last_verification_sent_at"])
        self.assertTrue(user.is_stale_unverified())

        cleanup_stale_unverified_accounts()

        self.assertFalse(
            User.objects.filter(email="newvisitor@example.com").exists()
        )

    def test_fresh_unverified_account_survives_cleanup(self):
        """Свежая незавершённая регистрация задачей не удаляется."""
        from core.tasks import cleanup_stale_unverified_accounts

        self._register_visitor()

        cleanup_stale_unverified_accounts()

        self.assertTrue(
            User.objects.filter(email="newvisitor@example.com").exists()
        )

    def test_verified_account_never_deleted_by_cleanup(self):
        """Подтверждённый аккаунт не удаляется задачей, даже «старый»."""
        from core.tasks import cleanup_stale_unverified_accounts

        self._register_visitor()
        user = User.objects.get(email="newvisitor@example.com")
        user.is_verified = True
        user.last_verification_sent_at = timezone.now() - timedelta(days=30)
        user.save(update_fields=["is_verified", "last_verification_sent_at"])

        cleanup_stale_unverified_accounts()

        self.assertTrue(
            User.objects.filter(email="newvisitor@example.com").exists()
        )

    def test_verification_code_expires_after_15_minutes(self):
        """Код из письма не принимается после истечения срока действия."""
        self._register_visitor()
        user = User.objects.get(email="newvisitor@example.com")
        code = EmailVerificationCode.objects.get(user=user, is_used=False).code

        # «Старим» код: срок действия прошёл
        EmailVerificationCode.objects.filter(user=user).update(
            expires_at=timezone.now() - timedelta(minutes=1)
        )

        response = self.client.post(
            self.VERIFY_URL,
            {
                "code1": code[0],
                "code2": code[1],
                "code3": code[2],
                "code4": code[3],
                "code5": code[4],
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Неверный код подтверждения")
        user.refresh_from_db()
        self.assertFalse(user.is_verified)

    def test_partner_files_deleted_with_stale_unverified_account(self):
        """
        Файлы незавершённой регистрации не остаются в хранилище.

        Сценарий: партнёр загрузил логотип и документы, но не ввёл код.
        Через час аккаунт удаляется задачей — вместе с файлами. Если файлы
        оставить, хранилище засоряется мусором от брошенных регистраций.
        """
        import tempfile
        import os
        from django.core.files.uploadedfile import SimpleUploadedFile
        from core.tasks import cleanup_stale_unverified_accounts
        from core.models import PartnerDocument
        from partner_app.models import PartnerProfile

        data = {
            "form_type": "partner",
            "email": "files@example.com",
            "password1": "Own3r!Pass2026",
            "password2": "Own3r!Pass2026",
            "company_name": "ООО Файлы",
            "short_name": "Файлы",
            "registration_type": "legal",
            "inn": "7707083893",
            "kpp": "770701001",
            "contact_person": "Иван Иванов",
            "phone": "+79990001122",
            "agree_terms": "on",
            "agree_user_agreement": "on",
            "agree_personal_data": "on",
        }
        logo = SimpleUploadedFile(
            "logo.png", b"png-data", content_type="image/png"
        )
        document = SimpleUploadedFile(
            "doc.pdf", b"pdf-data", content_type="application/pdf"
        )
        data["logo"] = logo
        data["documents"] = document
        response = self.client.post(self.REGISTER_URL, data)
        self.assertRedirects(response, self.VERIFY_URL)

        user = User.objects.get(email="files@example.com")
        profile = PartnerProfile.objects.get(user=user)
        doc = PartnerDocument.objects.get(user=user)

        # Файлы реально записаны в хранилище
        self.assertTrue(profile.logo.storage.exists(profile.logo.name))
        self.assertTrue(doc.document.storage.exists(doc.document.name))

        # Прошёл час — аккаунт уходит вместе с файлами
        user.last_verification_sent_at = timezone.now() - timedelta(hours=2)
        user.save(update_fields=["last_verification_sent_at"])

        cleanup_stale_unverified_accounts()

        self.assertFalse(
            User.objects.filter(email="files@example.com").exists()
        )
        # Файлы удалены из хранилища, а не остались «висеть»
        self.assertFalse(profile.logo.storage.exists(profile.logo.name))
        self.assertFalse(doc.document.storage.exists(doc.document.name))


class EventFormDescriptionFieldTestCase(SimpleTestCase):
    """Тесты конфигурации поля description в EventForm партнёра."""

    def test_event_form_description_field_has_help_text(self):
        """EventForm.description должен иметь справку о форматировании."""
        from partner_app.forms import EventForm

        form = EventForm()

        # Проверяем help_text
        self.assertIn("жирный", form.fields["description"].help_text)
        self.assertIn("курсив", form.fields["description"].help_text)
        self.assertIn("https://example.com", form.fields["description"].help_text)

    def test_event_form_description_field_has_textarea_attributes(self):
        """EventForm.description должен быть 10-строчным textarea с плейсхолдером."""
        from partner_app.forms import EventForm

        form = EventForm()
        widget = form.fields["description"].widget

        # Проверяем attributes
        self.assertEqual(widget.attrs.get("rows"), 10)
        self.assertIn("О мероприятии", widget.attrs.get("placeholder", ""))
        self.assertIn("**Что вас ждёт:**", widget.attrs.get("placeholder", ""))

    def test_event_form_enforces_package_description_limit(self):
        from partner_app.forms import EventForm

        package = EventPackage(name="Тестовый пакет", max_description_length=3)
        form = EventForm(
            data={"description": "четыре"},
            current_package=package,
        )

        self.assertEqual(form.fields["description"].widget.attrs["maxlength"], 3)
        self.assertFalse(form.is_valid())
        self.assertIn("3 символов", str(form.errors["description"]))

    def test_admin_form_enforces_selected_package_description_limit(self):
        package = EventPackage(name="Тестовый пакет", max_description_length=3)
        form = EventAdminForm(
            data={"description": "четыре"},
            instance=Event(package=package),
        )

        self.assertFalse(form.is_valid())
        self.assertIn("3 символов", str(form.errors["description"]))

    def test_description_font_size_is_selectable_from_standard_to_20px(self):
        from partner_app.forms import EventForm

        form = EventForm()

        self.assertEqual(form.fields["description_font_size"].initial, 13)
        self.assertEqual(
            [value for value, _label in form.fields["description_font_size"].choices],
            [13, 14, 15, 16, 17, 18, 19, 20],
        )
        self.assertTrue(form.fields["description_font_size"].help_text)

    def test_admin_form_exposes_description_font_size(self):
        form = EventAdminForm()

        self.assertIn("description_font_size", form.fields)
        self.assertTrue(form.fields["description_font_size"].choices)
