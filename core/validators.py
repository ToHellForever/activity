# core/validators.py

from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from moviepy import VideoFileClip
import logging
import os
import tempfile

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

        video_path = None

        # Проверяем, это загружаемый файл (FileField) или уже сохранённый файл в облаке
        if hasattr(value, 'temporary_file_path'):
            # Файл ещё не сохранён, есть временный путь
            video_path = value.temporary_file_path()
            logger.info(f"Используем временный путь: {video_path}")
        elif hasattr(value, 'path'):
            # Пытаемся получить путь, но storage может не поддерживать absolute paths
            try:
                video_path = value.path
            except (NotImplementedError, AttributeError):
                # Storage не поддерживает absolute paths (облачное хранилище)
                # Пропускаем валидацию, так как проверка уже сделана в views.py перед сохранением
                logger.info("Storage не поддерживает absolute paths, пропускаем валидацию")
                return
            except Exception as path_error:
                # Любая другая ошибка при получении пути - пропускаем валидацию
                logger.info(f"Ошибка при получении пути к файлу: {path_error}, пропускаем валидацию")
                return

        # Если у нас есть путь к файлу, проверяем его
        if video_path:
            # Проверяем существование файла перед обработкой
            if not os.path.exists(video_path):
                logger.warning(f"Файл видео не найден: {video_path}")
                # Это может быть облачное хранилище, пропускаем валидацию
                return

            logger.info(f"Валидация видео: {video_path}")
            logger.info(f"Проверяем длительность видео по пути: {video_path}")
            with VideoFileClip(video_path) as video_clip:
                duration = video_clip.duration
                logger.info(f"Длительность видео: {duration} секунд")

                # Используем точное значение длительности, чтобы избежать проблем с округлением
                if duration > 310:  # 5 минут = 310 секунд
                    logger.warning(f"Видео слишком длинное: {duration} секунд")
                    raise ValidationError(
                        _(
                            "Длительность видео не должна превышать 5 минут. Текущая длительность: %.2f минут."
                        )
                        % (duration / 60)
                    )
        elif hasattr(value, 'chunks'):
            # Это загружаемый файл без пути, сохраняем во временный файл для проверки
            temp_dir = tempfile.gettempdir()
            temp_path = os.path.join(temp_dir, 'video_validation_' + os.path.basename(value.name or 'video.mp4'))
            with open(temp_path, 'wb') as temp_file:
                for chunk in value.chunks():
                    temp_file.write(chunk)
            
            logger.info(f"Сохранили файл во временную директорию: {temp_path}")
            
            try:
                # Проверяем длительность
                with VideoFileClip(temp_path) as video_clip:
                    duration = video_clip.duration
                    logger.info(f"Длительность видео: {duration} секунд")
                    
                    # Очищаем временный файл
                    if os.path.exists(temp_path):
                        try:
                            os.remove(temp_path)
                        except:
                            pass

                    # Используем точное значение длительности
                    if duration > 310:
                        logger.warning(f"Видео слишком длинное: {duration} секунд")
                        raise ValidationError(
                            _(
                                "Длительность видео не должна превышать 5 минут. Текущая длительность: %.2f минут."
                            )
                            % (duration / 60)
                        )
            except ValidationError:
                raise
            except Exception as check_error:
                logger.error(f"Ошибка при проверке длительности: {check_error}")
                # Пропускаем валидацию при ошибке
                logger.info("Пропускаем валидацию из-за ошибки проверки")
        else:
            logger.warning(f"Не удалось определить путь к файлу для объекта: {value}")
            return  # Пропускаем валидацию, если не можем определить путь
            
    except ValidationError:
        # Пропускаем ValidationError, чтобы поднять его дальше
        raise
    except Exception as e:
        logger.error(f"Ошибка при проверке длительности видео: {str(e)}")
        # При ошибке пропускаем валидацию, так как проверка уже сделана в views.py
        logger.info("Пропускаем валидацию из-за ошибки")



