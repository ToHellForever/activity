# core/validators.py

from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from moviepy import VideoFileClip
import logging
import os

logger = logging.getLogger(__name__)


def validate_video_duration(value):
    """
    Проверяет, что длительность видео не превышает 5 минут.
    """
    if not value:
        return

    try:
        if not value:
            return

        # Используем временный путь, если файл еще не сохранен
        if hasattr(value, 'temporary_file_path'):
            video_path = value.temporary_file_path()
            logger.info(f"Используем временный путь: {video_path}")
        elif hasattr(value, 'path'):
            video_path = value.path
            logger.info(f"Используем путь к файлу: {video_path}")
        else:
            logger.warning(f"Не удалось определить путь к файлу для объекта: {value}")
            return  # Пропускаем валидацию, если не можем определить путь

        logger.info(f"Валидация видео: {video_path}")

        # Проверяем существование файла перед обработкой
        if not os.path.exists(video_path):
            logger.warning(f"Файл видео не найден: {video_path}")
            # Попробуем сохранить файл во временную директорию и проверить еще раз
            try:
                import tempfile
                temp_dir = tempfile.gettempdir()
                temp_path = os.path.join(temp_dir, os.path.basename(video_path))
                with open(temp_path, 'wb') as temp_file:
                    for chunk in value.chunks():
                        temp_file.write(chunk)
                video_path = temp_path
                logger.info(f"Сохранили файл во временную директорию: {video_path}")
            except Exception as save_error:
                logger.error(f"Не удалось сохранить файл во временную директорию: {save_error}")
                raise ValidationError(
                    _("Файл видео не найден. Пожалуйста, загрузите видео.")
                )

        logger.info(f"Проверяем длительность видео по пути: {video_path}")
        with VideoFileClip(video_path) as video_clip:
            duration = video_clip.duration
            logger.info(f"Длительность видео: {duration} секунд")

            # Используем точное значение длительности, чтобы избежать проблем с округлением
            logger.info(f"Длительность видео: {duration} секунд")

            if duration > 310:  # 5 минут = 300 секунд
                logger.warning(f"Видео слишком длинное: {duration} секунд")
                raise ValidationError(
                    _("Длительность видео не должна превышать 5 минут.")
                )
    except Exception as e:
        logger.error(f"Ошибка при проверке длительности видео: {str(e)}")
        raise ValidationError(_("Ошибка при проверке длительности видео: %s") % str(e))


def compress_video(input_path, output_path=None, target_size_mb=10):
    """
    Сжимает видео до целевого размера.
    """
    try:
        from moviepy import VideoFileClip
        import os
        import logging

        logger = logging.getLogger(__name__)

        if output_path is None:
            output_path = input_path

        with VideoFileClip(input_path) as video_clip:
            bitrate = f"{target_size_mb * 800}K"
            logger.info(f"Сжатие видео с битрейтом: {bitrate}")
            video_clip.write_videofile(
                output_path,
                codec="libx264",
                audio_codec="aac",
                bitrate=bitrate,
                logger=None,
            )
        logger.info(f"Видео успешно сжато: {output_path}")
        return True
    except Exception as e:
        logger.error(f"Ошибка при сжатии видео: {str(e)}")
        return False
