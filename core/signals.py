# signals.py
import time
import logging
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.conf import settings
from .models import Event, CustomUser
from venues.models import Venue
from .tasks import process_video_task
import os

logger = logging.getLogger(__name__)

def wait_for_file(file_path, max_attempts=20, delay=1):
    for _ in range(max_attempts):
        if os.path.exists(file_path):
            return True
        time.sleep(delay)
    return False

@receiver(post_save, sender=Event)
def process_event_video(sender, instance, **kwargs):
    logger.info(f"SIGNAL: process_event_video triggered for Event {instance.id}")
    
    # Проверяем, не вызвано ли это обновлением хэша после обработки
    # Если обновляются только поля хэша, пропускаем сигнал
    update_fields = kwargs.get('update_fields', None)
    if update_fields and 'processed_video_url_hash' in update_fields:
        logger.info(f"SIGNAL: Skipping - update_fields contains processed_video_url_hash for Event {instance.id}")
        return

    if not instance.video_url:
        logger.info(f"SIGNAL: No video_url for Event {instance.id}")
        return

    # Получаем текущий хэш видео для логирования
    current_hash = instance._get_video_hash(instance.video_url)
    stored_hash = instance.processed_video_url_hash
    logger.info(f"SIGNAL: Event {instance.id} - current_hash={current_hash}, stored_hash={stored_hash}")

    # Запускаем задачу если:
    # 1) stored_hash=None (новое видео или видео ещё не обработано)
    # 2) current_hash != stored_hash (хэш изменился)
    should_process = False
    if stored_hash is None and instance.video_url:
        # Новое видео или видео ещё не обработано
        should_process = True
        logger.info(f"SIGNAL: Event {instance.id} - new video (stored_hash=None), processing")
    elif current_hash is not None and stored_hash is not None and current_hash != stored_hash:
        # Хэш изменился - видео заменено
        should_process = True
        logger.info(f"SIGNAL: Event {instance.id} - hash changed from {stored_hash} to {current_hash}, processing")
    elif current_hash is not None and stored_hash is not None:
        # Хэш совпадает - видео уже обработано
        logger.info(f"SIGNAL: Event {instance.id} - hash unchanged, skipping")
    else:
        logger.info(f"SIGNAL: Event {instance.id} - hash mismatch or invalid, skipping")

    if should_process:
        logger.info(f"SIGNAL: Sending process_video_task.delay for Event {instance.id}")
        result = process_video_task.delay(
            model_name='Event',
            instance_id=instance.id,
            video_field_name='video_url',
            hash_field_name='processed_video_url_hash'
        )
        logger.info(f"SIGNAL: Task sent with ID: {result.id}")

@receiver(post_save, sender=Venue)
def process_venue_video(sender, instance, **kwargs):
    logger.info(f"SIGNAL: process_venue_video triggered for venue {instance.id}")
    
    # Проверяем, не вызвано ли это обновлением хэша после обработки
    # Если обновляются только поля хэша, пропускаем сигнал
    update_fields = kwargs.get('update_fields', None)
    if update_fields and 'processed_video_hash' in update_fields:
        logger.info(f"SIGNAL: Skipping - update_fields contains processed_video_hash for Event {instance.id}")
        return

    if not instance.video:
        logger.info(f"SIGNAL: No video for Event {instance.id}")
        return

    # Получаем текущий хэш видео для логирования
    current_hash = instance._get_video_hash(instance.video)
    stored_hash = instance.processed_video_hash
    logger.info(f"SIGNAL: Event {instance.id} - current_hash={current_hash}, stored_hash={stored_hash}")

    # Запускаем задачу если:
    # 1) stored_hash=None (новое видео или видео ещё не обработано)
    # 2) current_hash != stored_hash (хэш изменился)
    should_process = False
    if stored_hash is None and instance.video:
        # Новое видео или видео ещё не обработано
        should_process = True
        logger.info(f"SIGNAL: Event {instance.id} - new video (stored_hash=None), processing")
    elif current_hash is not None and stored_hash is not None and current_hash != stored_hash:
        # Хэш изменился - видео заменено
        should_process = True
        logger.info(f"SIGNAL: Event {instance.id} - hash changed from {stored_hash} to {current_hash}, processing")
    elif current_hash is not None and stored_hash is not None:
        # Хэш совпадает - видео уже обработано
        logger.info(f"SIGNAL: Event {instance.id} - hash unchanged, skipping")
    else:
        logger.info(f"SIGNAL: Event {instance.id} - hash mismatch or invalid, skipping")

    if should_process:
        logger.info(f"SIGNAL: Sending process_video_task.delay for Venue {instance.id}")
        result = process_video_task.delay(
            model_name='Venue',
            instance_id=instance.id,
            video_field_name='video',
            hash_field_name='processed_video_hash'
        )
        logger.info(f"SIGNAL: Task sent with ID: {result.id}")
        
@receiver(post_save, sender=CustomUser)
def process_video_business_card(sender, instance, **kwargs):
    logger.info(f"SIGNAL: process_video_business_card triggered for CustomUser {instance.id}")
    
    # Проверяем, не вызвано ли это обновлением хэша после обработки
    update_fields = kwargs.get('update_fields', None)
    if update_fields and 'processed_video_business_card_hash' in update_fields:
        logger.info(f"SIGNAL: Skipping - update_fields contains processed_video_business_card_hash for CustomUser {instance.id}")
        return

    if not instance.video_business_card:
        return

     # Запускаем задачу только если хэш не совпадает или отсутствует (видео новое/заменено)
    if instance._should_process_video(instance.video_business_card, instance.processed_video_business_card_hash):
        logger.info(f"SIGNAL: Sending process_video_task.delay for CustomUser {instance.id}")
        process_video_task.delay(
            model_name='CustomUser',
            instance_id=instance.id,
            video_field_name='video_business_card',
            hash_field_name='processed_video_business_card_hash'
        )
    else:
        logger.info(f"SIGNAL: Video business card already processed for CustomUser {instance.id}, skipping")