"""
Миксины для моделей Django.
"""

import hashlib
from django.db import models


class VideoWatermarkMixin:
    """Миксин для обработки видео с водяными знаками."""

    def _get_video_hash(self, video_field):
        """
        Возвращает MD5-хэш видео.
        Args:
            video_field: поле модели с видео (FileField).
        Returns:
            str: MD5-хэш файла или None, если файл отсутствует.
        """
        if not video_field:
            return None

        import os

        if not os.path.exists(video_field.path):
            return None

        with open(video_field.path, "rb") as f:
            return hashlib.md5(f.read()).hexdigest()

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
        if current_hash is None:
            return False
        return current_hash != hash_field
