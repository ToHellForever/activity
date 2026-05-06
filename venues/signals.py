# venues/signals.py
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.conf import settings
from .models import Venue
from core.tasks import process_video_task
import os

@receiver(pre_save, sender=Venue)
def clear_venue_video(sender, instance, **kwargs):
    if not instance.pk:
        return False

    try:
        old_instance = Venue.objects.get(pk=instance.pk)
    except Venue.DoesNotExist:
        return False

    # Если видео было удалено
    if old_instance.video and not instance.video:
        if os.path.isfile(old_instance.video.path):
            os.remove(old_instance.video.path)

@receiver(post_save, sender=Venue)
def process_venue_video(sender, instance, **kwargs):
    if not instance.video:
        return

    # Отладочный вывод
    print(f"DEBUG: Calling process_video_task with model_name='venues.Venue'")

    # Запускаем задачу только если хэш не совпадает или отсутствует (видео новое/заменено)
    if instance._should_process_video(instance.video, instance.processed_video_hash):
        process_video_task.delay(
            model_name="venues.Venue",
            instance_id=instance.id,
            video_field_name="video",
            hash_field_name="processed_video_hash",
        )