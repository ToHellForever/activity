# core/tasks.py

from celery import shared_task
from django.conf import settings
from django.apps import apps
import os
import logging
import time

logger = logging.getLogger(__name__)


def wait_for_file(file_path, max_attempts=20, delay=1):
    for _ in range(max_attempts):
        if os.path.exists(file_path):
            return True
        time.sleep(delay)
    return False


@shared_task(bind=True)
def process_event_video_task(self, event_id):
    """
    Асинхронная задача для обработки видео мероприятия.
    """
    try:
        from core.models import Event
        from core.validators import compress_video

        event = Event.objects.get(pk=event_id)

        # Обновляем статус обработки
        event.video_processing_status = "processing"
        event.save(update_fields=["video_processing_status"])

        video_field = event.video_url
        if not video_field:
            event.video_processing_status = "completed"
            event.save(update_fields=["video_processing_status"])
            return "Видео не требует обработки"

        video_path = video_field.path

        # Проверяем существование файла
        if not os.path.exists(video_path):
            logger.error(f"Файл видео не найден: {video_path}")
            event.video_processing_status = "failed"
            event.save(update_fields=["video_processing_status"])
            return f"Файл не найден: {video_path}"

        # Создаем временный путь для обработки с правильным расширением
        base, ext = os.path.splitext(video_path)
        temp_video_path = f"{base}_compressed{ext}"

        # Сжимаем видео и сохраняем во временный файл
        if not compress_video(video_path, temp_video_path):
            event.video_processing_status = "failed"
            event.save(update_fields=["video_processing_status"])
            return f"Ошибка: не удалось сжать видео: {video_path}"

        # Добавляем водяной знак
        actual_watermark_path = os.path.join(
            settings.BASE_DIR, "media", "watermark.png"
        )

        if not os.path.exists(actual_watermark_path):
            logger.error(f"Файл водяного знака не найден: {actual_watermark_path}")
            event.video_processing_status = "failed"
            event.save(update_fields=["video_processing_status"])
            return f"Файл водяного знака не найден"

        try:
            from core.utils import add_watermark_to_video

            if not add_watermark_to_video(
                temp_video_path, actual_watermark_path, temp_video_path
            ):
                logger.error(
                    f"Ошибка: не удалось добавить водяной знак к видео: {temp_video_path}"
                )
                event.video_processing_status = "failed"
                event.save(update_fields=["video_processing_status"])
                return f"Ошибка: не удалось добавить водяной знак к видео: {temp_video_path}"
        except Exception as e:
            logger.error(f"Исключение при добавлении водяного знака: {str(e)}")
            event.video_processing_status = "failed"
            event.save(update_fields=["video_processing_status"])
            return f"Исключение при добавлении водяного знака: {str(e)}"

        # Заменяем оригинальный файл обработанным
        try:
            if os.path.exists(video_path):
                os.remove(video_path)
            os.rename(temp_video_path, video_path)
        except Exception as e:
            logger.error(f"Ошибка при замене файлов: {str(e)}")
            event.video_processing_status = "failed"
            event.save(update_fields=["video_processing_status"])
            return f"Ошибка при замене файлов: {str(e)}"

        # Обновляем статус обработки
        event.video_processing_status = "completed"
        event.save(update_fields=["video_processing_status"])

        return f"Видео успешно обработано: {video_path}"
    except Exception as e:
        logger.error(f"Исключение при обработке видео: {str(e)}")
        event.video_processing_status = "failed"
        event.save(update_fields=["video_processing_status"])
        return f"Исключение при обработке видео: {str(e)}"


@shared_task(bind=True)
def process_video_task(
    self, model_name, instance_id, video_field_name, hash_field_name
):
    """
    Асинхронная задача для обработки видео (сжатие + водяной знак).
    """
    try:
        model = apps.get_model("core", model_name)
        instance = model.objects.get(pk=instance_id)

        video_field = getattr(instance, video_field_name)
        hash_field = getattr(instance, hash_field_name)

        if not video_field or not instance._should_process_video(
            video_field, hash_field
        ):
            return "Видео не требует обработки"

        video_path = video_field.path

        # Проверяем существование файла перед ожиданием
        if not os.path.exists(video_path):
            logger.error(f"Файл видео не найден: {video_path}")
            return f"Файл не найден: {video_path}"

        if not wait_for_file(video_path):
            logger.error(f"Файл видео не найден после ожидания: {video_path}")
            return f"Файл не найден: {video_path}"

        actual_watermark_path = os.path.join(
            settings.BASE_DIR, "media", "watermark.png"
        )

        if not os.path.exists(actual_watermark_path):
            logger.error(f"Файл водяного знака не найден: {actual_watermark_path}")
            return f"Файл водяного знака не найден"

        # Создаем временный путь для обработки
        temp_video_path = f"{video_path}.temp"

        # Сжимаем видео и сохраняем во временный файл
        if not compress_video(video_path, temp_video_path):
            return f"Ошибка: не удалось сжать видео: {video_path}"

        # Добавляем водяной знак на временный файл
        if not add_watermark_to_video(
            temp_video_path, actual_watermark_path, temp_video_path
        ):
            return f"Ошибка: не удалось добавить водяной знак к видео: {video_path}"

        # Заменяем оригинальный файл обработанным
        if os.path.exists(video_path):
            os.remove(video_path)
        os.rename(temp_video_path, video_path)

        setattr(instance, hash_field_name, instance._get_video_hash(video_field))
        instance.save(update_fields=[hash_field_name])

        return f"Видео успешно обработано: {video_path}"
    except Exception as e:
        logger.error(f"Исключение при обработке видео: {str(e)}")
        return f"Исключение при обработке видео: {str(e)}"
