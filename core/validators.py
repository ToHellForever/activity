"""
Валидаторы для моделей и форм.
"""

from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
import os
import tempfile
from moviepy import VideoFileClip


def validate_video_duration(value):
    """
    Валидатор для проверки длительности видео (не более 5 минут).
    """
    if not value:
        return

    try:
        # Проверяем, что файл существует
        if not hasattr(value, "file") or not value.file:
            return

        # Сохраняем файл во временный файл для обработки
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as temp_file:
            for chunk in value.file.chunks():
                temp_file.write(chunk)
            temp_path = temp_file.name

        try:
            # Используем moviepy для получения длительности видео
            clip = VideoFileClip(temp_path)
            duration = clip.duration
            clip.close()

            # Проверяем длительность
            if duration > 300:  # 300 секунд = 5 минут
                raise ValidationError(
                    _(
                        "Длительность видео не должна превышать 5 минут (текущая: %d секунд)."
                    )
                    % int(duration)
                )

        finally:
            # Удаляем временный файл
            try:
                os.unlink(temp_path)
            except OSError:
                pass

    except Exception as e:
        raise ValidationError(_("Ошибка при обработке видео: %s") % str(e))
