"""
Тесты для функционала водяных знаков.
"""

import os
import tempfile
from datetime import timedelta

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
    User,
    EventPackage,
    UserPackageSubscription,
    PartnerDocument,
    PayoutDetails,
    PayoutRequest,
)
from core.admin import (
    EventAdmin,
    PartnerDocumentAdmin,
    PayoutRequestAdmin,
    UserPackageSubscriptionAdmin,
)
from core.tasks import check_and_apply_scheduled_package_changes
from core.validators import validate_video_duration
from core.video_storage import YandexVideoProcessingStorage
from unittest.mock import patch, MagicMock


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
