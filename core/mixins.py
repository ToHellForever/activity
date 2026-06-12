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
        import logging
        from django.conf import settings
        logger = logging.getLogger(__name__)
        
        if not video_field:
            logger.debug("_get_video_hash: video_field is empty")
            return None
        try:
            logger.debug(f"_get_video_hash: trying to get path for {video_field}")
            video_path = video_field.path
            logger.debug(f"_get_video_hash: path={video_path}, exists={os.path.exists(video_path)}")
            with open(video_path, "rb") as f:
                return hashlib.md5(f.read()).hexdigest()
        except NotImplementedError:
            # Storage не поддерживает absolute paths (облачное хранилище или кастомное)
            # Пытаемся построить путь вручную через MEDIA_ROOT и MEDIA_TEMP_DIR
            logger.debug(f"_get_video_hash: trying manual path construction for {video_field.name}")
            possible_paths = [
                os.path.join(settings.MEDIA_ROOT, video_field.name),
                os.path.join(settings.MEDIA_ROOT, 'event_videos', os.path.basename(video_field.name)),
                os.path.join(getattr(settings, 'MEDIA_TEMP_DIR', os.path.join(settings.BASE_DIR, 'media_temp')), video_field.name),
                os.path.join(getattr(settings, 'MEDIA_TEMP_DIR', os.path.join(settings.BASE_DIR, 'media_temp')), 'event_videos', os.path.basename(video_field.name)),
                os.path.join(settings.BASE_DIR, video_field.name),
                os.path.join(settings.BASE_DIR, 'media', 'event_videos', os.path.basename(video_field.name)),
                os.path.join(settings.BASE_DIR, 'media_temp', os.path.basename(video_field.name)),
                os.path.join(settings.BASE_DIR, os.path.basename(video_field.name)),  # Просто в корне проекта
            ]
            for video_path in possible_paths:
                logger.debug(f"_get_video_hash: checking path={video_path}, exists={os.path.exists(video_path)}")
                if os.path.exists(video_path):
                    try:
                        with open(video_path, "rb") as f:
                            return hashlib.md5(f.read()).hexdigest()
                    except Exception as e:
                        logger.error(f"_get_video_hash: error reading path - {e}")
                        return None
            logger.warning(f"_get_video_hash: no valid path found for {video_field.name}")
            return None
        except Exception as e:
            logger.error(f"_get_video_hash: error - {e}")
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
