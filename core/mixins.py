"""
Миксины для моделей Django.
"""

import hashlib
import os
from django.db import models
from django.conf import settings


class VideoWatermarkMixin:
    """Миксин для обработки видео с водяными знаками."""

    def _get_video_hash(self, video_field):
        """
        Возвращает MD5-хэш видео.
        Args:
            video_field: поле модели с видео (FileField).
        Returns:
            str: MD5-хэш файла или None, если файл отсутствует или storage не поддерживает absolute paths.
        """
        if not video_field:
            return None
        try:
            with open(video_field.path, "rb") as f:
                return hashlib.md5(f.read()).hexdigest()
        except NotImplementedError:
            # Storage не поддерживает absolute paths (облачное хранилище)
            # Возвращаем None, чтобы не вызывать обработку
            return None

    def _should_process_video(self, video_field, hash_field):
        """
        Проверяет, нужно ли обрабатывать видео (если хэш изменился или отсутствует).
        Args:
            video_field: поле модели с видео (FileField).
            hash_field: поле модели с хэшем видео (CharField).
        Returns:
            bool: True, если видео нужно обработать.
        """
        current_hash = self._get_video_hash(video_field)
        # Если хэш не может быть получен (облачное хранилище), не обрабатываем
        if current_hash is None:
            return False
        return current_hash != hash_field

    def delete_old_video(self, video_field_name, hash_field_name):
        """Удаляет старый файл видео и обнуляет хэш."""
        video_field = getattr(self, video_field_name)
        if video_field:
            try:
                if os.path.exists(video_field.path):
                    try:
                        os.remove(video_field.path)
                    except Exception as e:
                        print(f"Ошибка удаления файла: {e}")
            except NotImplementedError:
                # Storage не поддерживает absolute paths (облачное хранилище)
                # Используем метод .delete() у FileField для удаления
                video_field.delete(save=False)
        setattr(self, hash_field_name, None)

    def delete_file_field(self, field_name):
        """
        Удаляет файл, связанный с указанным полем модели.
        Args:
            field_name: имя поля модели, содержащего файл (FileField или ImageField).
        """
        file_field = getattr(self, field_name)
        if file_field:
            try:
                if os.path.exists(file_field.path):
                    try:
                        os.remove(file_field.path)
                    except Exception as e:
                        print(f"Ошибка удаления файла {file_field.path}: {e}")
            except NotImplementedError:
                # Storage не поддерживает absolute paths (облачное хранилище)
                # Используем метод .delete() у FileField для удаления
                file_field.delete(save=False)


class ImageWatermarkMixin:
    """Миксин для добавления водяного знака на изображения."""

    def add_watermark_to_image_field(self, image_field_name, watermark_path=None):
        """
        Добавляет водяной знак на изображение, указанное в поле модели.
        Args:
            image_field_name: имя поля модели с изображением (ImageField).
            watermark_path: путь к файлу водяного знака. Если None, используется стандартный путь.
        """
        if not watermark_path:
            watermark_path = os.path.join(settings.MEDIA_ROOT, "watermark.png")

        image_field = getattr(self, image_field_name)
        if image_field and os.path.exists(watermark_path):
            try:
                if os.path.exists(image_field.path):
                    from core.utils import add_watermark_to_image
                    add_watermark_to_image(image_field.path, watermark_path, image_field.path)
            except NotImplementedError:
                # Storage не поддерживает absolute paths (облачное хранилище)
                # Не добавляем водяной знак локально
                pass
