# core/signals.py

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.conf import settings
from core.models import Event
from core.tasks import process_video_task
import os
import logging

logger = logging.getLogger(__name__)


def wait_for_file(file_path, max_attempts=20, delay=1):
    for _ in range(max_attempts):
        if os.path.exists(file_path):
            return True
        time.sleep(delay)
    return False


@receiver(post_save, sender=Event)
def process_event_video(sender, instance, created, **kwargs):
    """
    Сигнал для обработки видео мероприятия после сохранения.
    """
    if not created or not instance.video_url:
        return

    # Строим абсолютный путь к файлу
    video_path = os.path.join(settings.MEDIA_ROOT, instance.video_url.name)

    if not wait_for_file(video_path):
        logger.error(f"Файл видео не найден после ожидания: {video_path}")
        return

    # Запускаем асинхронную задачу Celery для обработки видео
    from core.tasks import process_event_video_task

    process_event_video_task.delay(instance.id)
