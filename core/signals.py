# signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.conf import settings
from .models import Event, CustomUser
from .tasks import process_video_task
import os

def wait_for_file(file_path, max_attempts=20, delay=1):
    for _ in range(max_attempts):
        if os.path.exists(file_path):
            return True
        time.sleep(delay)
    return False

@receiver(post_save, sender=Event)
def process_event_video(sender, instance, **kwargs):
    if not instance.video_url:
        return

    # Запускаем задачу только если хэш не совпадает или отсутствует (видео новое/заменено)
    if instance._should_process_video(instance.video_url, instance.processed_video_url_hash):
        process_video_task.delay(
            model_name='Event',
            instance_id=instance.id,
            video_field_name='video_url',
            hash_field_name='processed_video_url_hash'
        )


@receiver(post_save, sender=CustomUser)
def process_video_business_card(sender, instance, **kwargs):
    if not instance.video_business_card:
        return

     # Запускаем задачу только если хэш не совпадает или отсутствует (видео новое/заменено)
    if instance._should_process_video(instance.video_business_card, instance.processed_video_business_card_hash):
        process_video_task.delay(
            model_name='CustomUser',
            instance_id=instance.id,
            video_field_name='video_business_card',
            hash_field_name='processed_video_business_card_hash'
        )