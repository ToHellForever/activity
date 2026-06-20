"""
Тесты для функционала водяных знаков.
"""

import os
import tempfile
from django.test import TestCase, override_settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.exceptions import ValidationError
from PIL import Image, ImageDraw
from core.utils import add_watermark_to_image, add_watermark_to_video
from core.models import Event, User
from core.validators import validate_video_duration
from unittest.mock import patch, MagicMock


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
