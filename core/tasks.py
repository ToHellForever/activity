# tasks.py
from celery import shared_task
from django.apps import apps
import os
import logging
import time
from django.utils import timezone
from django.conf import settings
from core.models import Event, Ticket


logger = logging.getLogger(__name__)

def wait_for_file(file_path, max_attempts=20, delay=1):
    for _ in range(max_attempts):
        if os.path.exists(file_path):
            return True
        time.sleep(delay)
    return False

@shared_task(bind=True)
def process_video_task(
    self, model_name, instance_id, video_field_name, hash_field_name
):
    try:
        # Разбираем model_name в формате "app_label.model_name"
        if isinstance(model_name, str) and '.' in model_name:
            parts = model_name.split('.')
            if len(parts) == 2:
                app_label, model_name = parts
            else:
                # Если формат неожиданный, используем venues по умолчанию для Venues
                if 'Venue' in model_name:
                    app_label = 'venues'
                else:
                    app_label = 'core'
        else:
            # Если нет точки, используем venues по умолчанию для Venues
            if 'Venue' in str(model_name):
                app_label = 'venues'
            else:
                app_label = 'core'

        model = apps.get_model(app_label, model_name)
        instance = model.objects.get(pk=instance_id)
        
        video_field = getattr(instance, video_field_name)
        hash_field = getattr(instance, hash_field_name)

        # Двойная проверка на случай гонки сигналов/задач Celery
        if not video_field or not instance._should_process_video(video_field, hash_field):
            return f"Видео не требует обработки: {model_name} {instance_id}"

        video_path = video_field.path

        if not os.path.exists(video_path) and not wait_for_file(video_path):
            logger.error(f"Файл видео не найден: {video_path}")
            return f"Файл не найден: {video_path}"

        # Пути для временных файлов (в той же директории для атомарности)
        base_dir = os.path.dirname(video_path)
        base_name = os.path.splitext(os.path.basename(video_path))[0]
        temp_video_path = os.path.join(base_dir, f"{base_name}_temp.mp4")
        watermarked_video_path = os.path.join(base_dir, f"{base_name}_watermarked.mp4")

        # Сжимаем видео и сохраняем во временный файл
        from .validators import compress_video
        if not compress_video(video_path, temp_video_path):
            return f"Ошибка: не удалось сжать видео: {video_path}"

        # Добавляем водяной знак на временный файл и сохраняем в отдельный файл
        from .utils import add_watermark_to_video
        
        watermark_path = os.path.join(settings.MEDIA_ROOT, "watermark.png")
        if not os.path.exists(watermark_path):
            logger.error(f"Файл водяного знака не найден по пути: {watermark_path}")
            return f"Файл водяного знака не найден по пути: {watermark_path}"
        
        if not add_watermark_to_video(
            temp_video_path,
            watermark_path,
            watermarked_video_path,
        ):
            return f"Ошибка: не удалось добавить водяной знак к видео: {video_path}"

        # Атомарная замена файла (для избежания частичной записи при ошибке)
        try:
            # Сохраняем исходный файл как резервную копию (опционально для безопасности)
            backup_path = f"{video_path}.bak"
            if os.path.exists(backup_path):
                os.remove(backup_path)  # Удаляем старую бакап если есть (редко нужно)
            
            os.replace(video_path, backup_path)  # Переименовываем исходный в бакап

            # Перемещаем обработанный файл на место исходного с правильным именем/расширением!
            os.replace(watermarked_video_path, video_path) 
            
            # Удаляем временный файл сжатия и бакап (если всё ок)
            for p in [temp_video_path]:
                if os.path.exists(p):
                    os.remove(p)
            
            # Удаляем бакап только если новый файл успешно записан и имеет ненулевой размер!
            if os.path.exists(video_path) and os.path.getsize(video_path) > 0 and os.path.exists(backup_path):
                os.remove(backup_path)

        except Exception as e:
            logger.error(f"Ошибка при замене файлов: {str(e)}")
            return f"Ошибка при замене файлов: {str(e)}"

        # Обновляем хэш обработанного видео в БД (только если всё прошло успешно!)
        new_hash = instance._get_video_hash(video_field)
        setattr(instance, hash_field_name, new_hash)
        instance.save(update_fields=[hash_field_name])

        return f"Видео успешно обработано: {video_path}"
    except Exception as e:
        logger.error(f"Исключение при обработке видео: {str(e)}")
        return f"Исключение при обработке видео: {str(e)}"

@shared_task
def close_event_sales():
    """
    Задача Celery для автоматического закрытия продаж билетов
    за указанное количество часов до начала мероприятия.
    Использует значение auto_close_sales_hours из модели Event.
    """

    now = timezone.now()
    events = Event.objects.filter(status="active")

    for event in events:
        # Проверяем, нужно ли автоматически закрывать продажи для этого мероприятия
        if event.auto_close_sales_hours > 0:
            # Вычисляем время закрытия продаж на основе настроек мероприятия
            close_time = event.date_time - timezone.timedelta(hours=event.auto_close_sales_hours)

            # Если текущее время больше или равно времени закрытия
            if now >= close_time:
                logger.info(f"Продажи билетов для мероприятия {event.title} закрыты за {event.auto_close_sales_hours} часов до начала.")

    return f"Проверка и закрытие продаж выполнены: {now}"
