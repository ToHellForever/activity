# signals.py
import time
import logging
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.conf import settings
from .models import Event, CustomUser, Order, OrderTicket
from partner_app.models import PartnerProfile
from .tasks import process_video_task
import os

logger = logging.getLogger(__name__)


class _OrderSyncContext:
    """Потокобезопасный контекст для предотвращения рекурсии в сигналах Order."""
    def __init__(self):
        import threading
        self._local = threading.local()

    @property
    def syncing(self):
        return getattr(self._local, 'active', False)

    @syncing.setter
    def syncing(self, value):
        self._local.active = value

    def __enter__(self):
        self.syncing = True

    def __exit__(self, *args):
        self.syncing = False


_order_sync = _OrderSyncContext()


def wait_for_file(file_path, max_attempts=20, delay=1):
    for _ in range(max_attempts):
        if os.path.exists(file_path):
            return True
        time.sleep(delay)
    return False


@receiver(post_save, sender=Order)
def create_order_tickets(sender, instance, created, **kwargs):
    """Автоматически создаёт OrderTicket для каждого билета в заказе."""
    with _order_sync:
        if _order_sync.syncing:
            return

        if created:
            quantity = instance.quantity or 1
            # Создаём билеты
            tickets_to_create = []
            for i in range(1, quantity + 1):
                tickets_to_create.append(
                    OrderTicket(order=instance, ticket_number=i, attended=False)
                )
            if tickets_to_create:
                OrderTicket.objects.bulk_create(tickets_to_create)
                logger.info("Created %d OrderTicket(s) for Order %s", quantity, instance.id)

        # Синхронизируем quantity при изменении
        current_count = instance.tickets.count()
        if current_count != instance.quantity:
            if current_count < instance.quantity:
                # Нужно добавить билеты
                for i in range(current_count + 1, instance.quantity + 1):
                    OrderTicket.objects.create(order=instance, ticket_number=i)
                logger.info("Added %d ticket(s) to Order %s", instance.quantity - current_count, instance.id)
            elif current_count > instance.quantity:
                # Удаляем лишние билеты (оставляем первые quantity)
                instance.tickets.filter(ticket_number__gt=instance.quantity).delete()
                logger.info("Removed %d excess ticket(s) from Order %s", current_count - instance.quantity, instance.id)


@receiver(post_save, sender=Event)
def process_event_video(sender, instance, **kwargs):
    logger.info("SIGNAL: process_event_video triggered for Event %s", instance.id)
    
    # Пропускаем сигнал, если файл ещё не сохранён (внутренняя синхронизация)
    if getattr(instance, '_avoid_file_deletion', False):
        logger.info("SIGNAL: Skipping - _avoid_file_deletion is set for Event %s", instance.id)
        return
    
    update_fields = kwargs.get('update_fields', None)
    if update_fields:
        if 'processed_video_url_hash' in update_fields:
            logger.info("SIGNAL: Skipping - processed_video_url_hash for Event %s", instance.id)
            return
        if 'video_processing_status' in update_fields:
            logger.info("SIGNAL: Skipping - video_processing_status for Event %s", instance.id)
            return
        if 'video_url' in update_fields:
            status = instance.video_processing_status
            if status in ('processing', 'completed', 'failed'):
                logger.info("SIGNAL: Skipping - status is '%s' for Event %s", status, instance.id)
                return

    if not instance.video_url:
        logger.info("SIGNAL: No video_url for Event %s", instance.id)
        return

    status = instance.video_processing_status
    if status == 'processing':
        logger.info("SIGNAL: Skipping - status is '%s' for Event %s", status, instance.id)
        return

    current_hash = instance._get_video_hash(instance.video_url)
    stored_hash = instance.processed_video_url_hash
    logger.info("SIGNAL: Event %s - current_hash=%s, stored_hash=%s", instance.id, current_hash, stored_hash)

    should_process = False
    if stored_hash is None and instance.video_url:
        should_process = True
        logger.info("SIGNAL: Event %s - new video, processing", instance.id)
    elif current_hash is not None and stored_hash is not None and current_hash != stored_hash:
        should_process = True
        logger.info("SIGNAL: Event %s - hash changed, processing", instance.id)
    elif current_hash is not None and stored_hash is not None:
        logger.info("SIGNAL: Event %s - hash unchanged, skipping", instance.id)
    else:
        logger.info("SIGNAL: Event %s - hash mismatch, skipping", instance.id)

    if should_process:
        logger.info("SIGNAL: Sending process_video_task.delay for Event %s", instance.id)
        result = process_video_task.delay(
            model_name='Event',
            instance_id=instance.id,
            video_field_name='video_url',
            hash_field_name='processed_video_url_hash',
            status_field_name='video_processing_status'
        )
        logger.info("SIGNAL: Task sent with ID: %s", result.id)
        
@receiver(post_save, sender=PartnerProfile)
def process_video_business_card(sender, instance, **kwargs):
    logger.info("SIGNAL: process_video_business_card triggered for PartnerProfile %s", instance.id)
    
    update_fields = kwargs.get('update_fields', None)
    if update_fields:
        if 'processed_video_business_card_hash' in update_fields:
            logger.info("SIGNAL: Skipping - hash for PartnerProfile %s", instance.id)
            return
        if 'video_business_card_processing_status' in update_fields:
            logger.info("SIGNAL: Skipping - status for PartnerProfile %s", instance.id)
            return
        if 'video_business_card' in update_fields:
            status = instance.video_business_card_processing_status
            if status in ('processing', 'completed'):
                logger.info("SIGNAL: Skipping - status '%s' for PartnerProfile %s", status, instance.id)
                return

    if not instance.video_business_card:
        return

    if instance._should_process_video(instance.video_business_card, instance.processed_video_business_card_hash):
        logger.info("SIGNAL: Sending process_video_task.delay for PartnerProfile %s", instance.id)
        process_video_task.delay(
            model_name='PartnerProfile',
            instance_id=instance.id,
            video_field_name='video_business_card',
            hash_field_name='processed_video_business_card_hash',
            status_field_name='video_business_card_processing_status'
        )
    else:
        logger.info("SIGNAL: Video business card already processed for PartnerProfile %s, skipping", instance.id)