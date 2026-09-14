"""
Тесты для функционала водяных знаков.
"""

import os
import tempfile
from datetime import timedelta

from django.test import SimpleTestCase, TestCase, override_settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.exceptions import ValidationError
from django.utils import timezone
from PIL import Image, ImageDraw
from core.utils import add_watermark_to_image, add_watermark_to_video
from core.models import Event, User, EventPackage, UserPackageSubscription
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
            place="Test Place",
            organizer=self.user,
            image=event_image,
        )
        event.save()

        # Проверяем, что изображение сохранено
        self.assertTrue(event.image)
        self.assertTrue(os.path.exists(event.image.path))

    def tearDown(self):
        """Удаляем временные файлы."""
        if os.path.exists(self.watermark_path):
            os.remove(self.watermark_path)

    def test_validate_video_duration(self):
        """Тест валидации длительности видео."""
        # Создаем мок для VideoFileClip
        mock_video_clip = MagicMock()
        mock_video_clip.__enter__.return_value = mock_video_clip
        mock_video_clip.duration = 301  # 5 минут и 1 секунда

        # Создаем временный файл
        test_video_path = tempfile.mktemp(suffix=".mp4")
        with open(test_video_path, "wb") as f:
            f.write(os.urandom(1024 * 1024))  # 1MB заглушка

        # Создаем мок для SimpleUploadedFile
        mock_file = MagicMock()
        mock_file.path = test_video_path

        # Проверяем, что валидатор выдает ошибку для видео длиннее 5 минут
        with patch("moviepy.VideoFileClip", return_value=mock_video_clip):
            with self.assertRaises(ValidationError):
                validate_video_duration(mock_file)

        # Проверяем, что валидатор не выдает ошибку для видео короче 5 минут
        mock_video_clip.duration = 299  # 4 минуты и 59 секунд
        with patch("moviepy.VideoFileClip", return_value=mock_video_clip):
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
