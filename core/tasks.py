
from celery import shared_task
from django.db.models import Count
from core.models import Ticket, Order
import logging
from django.apps import apps
import os
import time
from django.utils import timezone
from django.conf import settings
from core.models import Event, Ticket
from venues.models import Venue
from django.core.management import call_command
logger = logging.getLogger(__name__)

@shared_task
def check_race_conditions_task():
    """
    Периодическая задача для проверки согласованности данных и обнаружения гонок.
    Запускается через Celery Beat.
    """
    logger.info("Starting scheduled race condition check...")

    try:
        # Вызываем команду Django для проверки
        call_command("check_race_conditions")
        logger.info("Scheduled race condition check completed successfully")
        return "Success: No race condition issues detected"
    except Exception as e:
        logger.error(f"Error during scheduled race condition check: {str(e)}")
        return f"Error: {str(e)}"

@shared_task
def monitor_ticket_consistency():
    """
    Расширенный мониторинг согласованности данных о билетах.
    """
    logger.info("Starting ticket consistency monitoring...")

    issues = []

    try:
        # Проверяем все билеты
        for ticket in Ticket.objects.all():
            # Прямой расчет проданных билетов
            db_sold = sum(order.quantity for order in ticket.orders.all())
            calc_available = ticket.available_quantity - db_sold

            # Расчет через метод модели
            model_available = ticket.get_available_count()

            if calc_available != model_available:
                issues.append(
                    {
                        "ticket_id": ticket.id,
                        "name": ticket.name,
                        "direct_calc": calc_available,
                        "model_calc": model_available,
                        "type": "calculation_mismatch",
                    }
                )

            # Проверяем на отрицательное количество
            if model_available < 0:
                issues.append(
                    {
                        "ticket_id": ticket.id,
                        "name": ticket.name,
                        "available": model_available,
                        "type": "negative_quantity",
                    }
                )

        if issues:
            error_msg = f"Found {len(issues)} consistency issues: {issues}"
            logger.error(error_msg)
            return error_msg
        else:
            logger.info("Ticket consistency monitoring: All tickets are consistent")
            return "Success: All tickets are consistent"

    except Exception as e:
        logger.error(f"Ticket consistency monitoring error: {str(e)}")
        return f"Error: {str(e)}"

@shared_task
def clean_up_inconsistent_tickets():
    """
    Исправление несогласованных данных о билетах.
    """
    logger.info("Starting ticket data cleanup...")

    try:
        fixed_count = 0

        for ticket in Ticket.objects.all():
            # Проверяем на отрицательное доступное количество
            available = ticket.get_available_count()
            if available < 0:
                # Исправляем, увеличивая available_quantity
                needed = abs(available)
                ticket.available_quantity += needed
                ticket.save()
                fixed_count += 1
                logger.warning(
                    f"Fixed ticket {ticket.id}: added {needed} to available_quantity"
                )

        logger.info(f"Ticket data cleanup: Fixed {fixed_count} tickets")
        return f"Success: Fixed {fixed_count} tickets"

    except Exception as e:
        logger.error(f"Ticket data cleanup error: {str(e)}")
        return f"Error: {str(e)}"

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
    """
    Асинхронная обработка видео:
    1. Сжимает видео
    2. Добавляет водяной знак
    3. Загружает в Яндекс Cloud (если включен)
    4. Удаляет временный локальный файл
    """
    logger.info(f"CELERY TASK STARTED: process_video_task for {model_name} {instance_id}")
    try:
        # Разбираем model_name в формате "app_label.model_name"
        if isinstance(model_name, str) and "." in model_name:
            parts = model_name.split(".")
            if len(parts) == 2:
                app_label, model_name = parts
            else:
                if "Venue" in model_name:
                    app_label = "venues"
                else:
                    app_label = "core"
        else:
            if "Venue" in str(model_name):
                app_label = "venues"
            else:
                app_label = "core"

        model = apps.get_model(app_label, model_name)
        try:
            instance = model.objects.get(pk=instance_id)
        except model.DoesNotExist:
            logger.error(f"CELERY TASK: {model_name} {instance_id} does not exist")
            return f"{model_name} {instance_id} does not exist"

        video_field = getattr(instance, video_field_name)
        hash_field = getattr(instance, hash_field_name)

        if not video_field:
            logger.info(f"CELERY TASK: No video for {model_name} {instance_id}")
            return f"Видео не требуется: {model_name} {instance_id}"

        # Получаем путь к временному файлу
        video_path = video_field.path
        logger.info(f"CELERY TASK: Processing video for {model_name} {instance_id}, video_path={video_path}")

        if not os.path.exists(video_path):
            logger.error(f"Файл видео не найден: {video_path}")
            return f"Файл не найден: {video_path}"

        # Проверяем размер файла
        file_size = os.path.getsize(video_path)
        logger.info(f"CELERY TASK: Video file size: {file_size} bytes")
        if file_size == 0:
            logger.error(f"Файл видео пуст: {video_path}")
            return f"Файл видео пуст: {video_path}"

        # Пути для временных файлов
        base_dir = os.path.dirname(video_path)
        base_name = os.path.splitext(os.path.basename(video_path))[0]
        compressed_video_path = os.path.join(base_dir, f"{base_name}_compressed.mp4")
        watermarked_video_path = os.path.join(base_dir, f"{base_name}_watermarked.mp4")

        # 1. Сжимаем видео
        logger.info(f"CELERY TASK: Compressing video {video_path}")
        from .utils import compress_video
        if not compress_video(video_path, compressed_video_path):
            logger.error(f"Ошибка при сжатии видео: {video_path}")
            return f"Ошибка при сжатии видео: {video_path}"
        logger.info(f"CELERY TASK: Video compressed to {compressed_video_path}")

        # 2. Добавляем водяной знак
        # Используем абсолютный путь к watermark
        watermark_path = os.path.join(os.path.dirname(__file__), '..', 'media', 'watermark.png')
        watermark_path = os.path.abspath(watermark_path)
        logger.info(f"CELERY TASK: Looking for watermark at {watermark_path}")
        if not os.path.exists(watermark_path):
            # Пробуем альтернативный путь
            watermark_path = os.path.join(settings.BASE_DIR, 'media', 'watermark.png')
            logger.info(f"CELERY TASK: Trying alternative path: {watermark_path}")
        if not os.path.exists(watermark_path):
            logger.error(f"Файл водяного знака не найден: {watermark_path}")
            # Удаляем сжатое видео и возвращаем ошибку
            if os.path.exists(compressed_video_path):
                os.remove(compressed_video_path)
            return f"Файл водяного знака не найден: {watermark_path}"

        logger.info(f"CELERY TASK: Adding watermark to {compressed_video_path}")
        from .utils import add_watermark_to_video
        if not add_watermark_to_video(compressed_video_path, watermark_path, watermarked_video_path):
            logger.error(f"Ошибка при добавлении водяного знака: {compressed_video_path}")
            # Удаляем сжатое видео и возвращаем ошибку
            if os.path.exists(compressed_video_path):
                os.remove(compressed_video_path)
            return f"Ошибка при добавлении водяного знака: {compressed_video_path}"
        logger.info(f"CELERY TASK: Watermark added to {watermarked_video_path}")

        # 3. Загружаем в Яндекс Cloud если включен
        if getattr(settings, 'USE_YANDEX_CLOUD', False):
            logger.info(f"CELERY TASK: Uploading to Yandex Cloud")
            try:
                import boto3
                from botocore.client import Config
                
                # Создаем S3 клиент для Yandex Cloud
                s3_client = boto3.client(
                    's3',
                    endpoint_url=settings.AWS_S3_ENDPOINT_URL,
                    aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                    aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                    region_name=settings.AWS_S3_REGION_NAME,
                    config=Config(signature_version='s3v4'),
                )

                # Загружаем файл напрямую через boto3
                cloud_name = video_field.name
                with open(watermarked_video_path, 'rb') as f:
                    file_content = f.read()
                    s3_client.put_object(
                        Bucket=settings.AWS_STORAGE_BUCKET_NAME,
                        Key=cloud_name,
                        Body=file_content,
                        ContentType='video/mp4',
                    )
                logger.info(f"CELERY TASK: Uploaded to Yandex Cloud at {cloud_name}")
                
                # Обновляем путь в модели на Cloud путь
                setattr(instance, video_field_name, cloud_name)
                instance.save(update_fields=[video_field_name])
                
                # Удаляем локальный файл из media_temp после успешной загрузки
                if os.path.exists(video_path):
                    os.remove(video_path)
                    logger.info(f"CELERY TASK: Deleted local video file {video_path}")
                    
            except Exception as e:
                logger.error(f"Ошибка при загрузке в Yandex Cloud: {e}", exc_info=True)
                # Удаляем временные файлы
                for p in [compressed_video_path, watermarked_video_path, video_path]:
                    if os.path.exists(p):
                        try:
                            os.remove(p)
                        except Exception:
                            pass
                return f"Ошибка при загрузке в Cloud: {e}"
        else:
            # Локальный режим - перемещаем обработанный файл
            logger.info(f"CELERY TASK: Local mode, replacing video file")
            try:
                os.replace(watermarked_video_path, video_path)
                # Удаляем исходный файл
                if os.path.exists(video_path + '.bak'):
                    os.remove(video_path + '.bak')
            except Exception as e:
                logger.error(f"Ошибка при замене файла: {e}")
                return f"Ошибка при замене файла: {e}"

        # 4. Обновляем хэш в БД
        new_hash = instance._get_video_hash(getattr(instance, video_field_name))
        setattr(instance, hash_field_name, new_hash)
        instance.save(update_fields=[hash_field_name])
        logger.info(f"CELERY TASK: Updated hash to {new_hash}")

        # 5. Удаляем временные локальные файлы (сжатое и с водяным знаком)
        # video_path уже удалён после загрузки в Cloud
        for p in [compressed_video_path, watermarked_video_path]:
            if os.path.exists(p):
                try:
                    os.remove(p)
                    logger.info(f"CELERY TASK: Deleted temp file {p}")
                except Exception as e:
                    logger.warning(f"Не удалось удалить {p}: {e}")

        logger.info(f"CELERY TASK: Successfully processed video for {model_name} {instance_id}")
        return f"Видео успешно обработано: {instance_id}"
    except Exception as e:
        logger.error(f"Исключение при обработке видео: {str(e)}", exc_info=True)
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
            close_time = event.date_time - timezone.timedelta(
                hours=event.auto_close_sales_hours
            )

            # Если текущее время больше или равно времени закрытия
            if now >= close_time:
                logger.info(
                    f"Продажи билетов для мероприятия {event.title} закрыты за {event.auto_close_sales_hours} часов до начала."
                )

    return f"Проверка и закрытие продаж выполнены: {now}"

@shared_task
def check_unpaid_tickets():
    """
    Задача Celery для проверки неоплаченных билетов.
    Возвращает билет в продажу, если он не был оплачен в течение 10 минут.
    """
    from django.utils import timezone
    from core.models import Order, Ticket

    now = timezone.now()
    unpaid_orders = Order.objects.filter(
        payment_status__in=["pending"],
        is_paid=False,
        created_at__lte=now - timezone.timedelta(minutes=10)
    )

    for order in unpaid_orders:
        # Возвращаем билеты в продажу
        ticket = order.ticket
        ticket.available_quantity += order.quantity
        ticket.save()

        # Обновляем статус заказа
        order.payment_status = "canceled"
        order.save()

        logger.info(f"Заказ {order.id} отменен из-за неоплаты. Билеты возвращены в продажу.")

@shared_task
def check_reserved_tickets():
    """
    Задача Celery для проверки забронированных билетов.
    Отправляет напоминания об оплате за 48 и 24 часа до мероприятия.
    """
    from django.core.mail import send_mail
    from django.template.loader import render_to_string
    from django.utils.html import strip_tags

    now = timezone.now()

    # Получаем все забронированные заказы, которые еще не оплачены
    reserved_orders = Order.objects.filter(
        payment_status="reserved", is_paid=False
    ).select_related("ticket__event")

    for order in reserved_orders:
        event = order.ticket.event
        time_until_event = (event.date_time - now).total_seconds() / 3600  # в часах

        # Отправляем напоминание за 48 часов
        if 48 >= time_until_event > 47:
            send_reservation_reminder(order, 48)
            logger.info(f"Отправлено напоминание за 48 часов для заказа {order.id}")

        # Отправляем напоминание за 24 часа
        elif 24 >= time_until_event > 23:
            send_reservation_reminder(order, 24)
            logger.info(f"Отправлено напоминание за 24 часа для заказа {order.id}")
        # Проверяем, не истек ли срок оплаты
        if order.payment_deadline and now > order.payment_deadline:
            # Отменяем заказ и освобождаем билеты
            order.payment_status = "canceled"
            order.is_paid = False
            order.save()

            # Увеличиваем доступное количество билетов
            ticket = order.ticket
            ticket.available_quantity += order.quantity
            ticket.save()

            # Уведомляем пользователя об отмене
            send_reservation_cancelation(order)
            logger.info(
                f"Заказ {order.id} отменен из-за просрочки оплаты. Билеты возвращены в продажу"
            )

    return f"Проверка забронированных билетов выполнена: {now}"

def send_reservation_reminder(order, hours_until_event):
    """Отправляет уведомление о необходимости оплаты забронированного билета."""
    from django.urls import reverse
    from django.contrib.sites.shortcuts import get_current_site

    user_email = order.participant_data.get("email")
    if not user_email:
        return

    event = order.ticket.event

    # Генерируем ссылку для оплаты
    payment_link = generate_payment_link(order)

    subject = f"Напоминание об оплате билета на мероприятие {event.title}"

    context = {
        "order": order,
        "event": event,
        "hours_until_event": hours_until_event,
        "payment_link": payment_link,
        "site_name": get_current_site(None).name,
    }

    html_message = render_to_string("emails/reservation_reminder.html", context)
    plain_message = strip_tags(html_message)

    send_mail(
        subject,
        plain_message,
        "noreply@eventplatform.com",
        [user_email],
        html_message=html_message,
    )

def send_reservation_cancelation(order):
    """Отправляет уведомление об отмене бронирования из-за просрочки оплаты."""
    user_email = order.participant_data.get("email")
    if not user_email:
        return

    event = order.ticket.event

    subject = f"Отмена бронирования билета на мероприятие {event.title}"

    context = {
        "order": order,
        "event": event,
    }

    html_message = render_to_string("emails/reservation_canceled.html", context)
    plain_message = strip_tags(html_message)

    send_mail(
        subject,
        plain_message,
        "noreply@eventplatform.com",
        [user_email],
        html_message=html_message,
    )

def generate_payment_link(order, request=None):
    """Генерирует ссылку для оплаты забронированного билета."""
    from django.urls import reverse
    from django.contrib.sites.shortcuts import get_current_site

    # Используем URL покупки билета без указания event_id
    url = reverse("buy_ticket", args=[order.ticket.event.id])

    # Добавляем параметры для идентификации заказа
    payment_url = f"{url}?reserve_order={order.id}"

    # Получаем полный URL с доменом
    if request:
        # Если передан request, используем его для получения домена
        current_site = get_current_site(request)
    else:
        # Если request не передан, получаем текущий сайт без request
        current_site = get_current_site(None)

    full_url = f"http://{current_site.domain}{payment_url}"

    return full_url

@shared_task
def check_and_apply_scheduled_package_changes():
    """
    Задача Celery для проверки и применения запланированных изменений пакетов.
    Выполняется периодически для проверки, не настало ли время смены пакета.
    """
    from core.models import UserPackageSubscription
    from django.utils import timezone

    logger.info("Starting scheduled package change check...")

    try:
        now = timezone.now()
        subscriptions = UserPackageSubscription.objects.filter(
            scheduled_change_to__isnull=False,
            scheduled_change_date__lte=now,
            is_active=True
        )

        applied_changes = 0

        for subscription in subscriptions:
            try:
                new_subscription = subscription.apply_scheduled_change()
                if new_subscription:
                    applied_changes += 1
                    logger.info(f"Applied scheduled package change for user {subscription.user.email}: {subscription.package.name} -> {new_subscription.package.name}")
            except Exception as e:
                logger.error(f"Error applying scheduled package change for subscription {subscription.id}: {str(e)}")
                continue

        logger.info(f"Scheduled package change check completed. Applied {applied_changes} changes.")
        return f"Success: Applied {applied_changes} scheduled package changes"

    except Exception as e:
        logger.error(f"Error during scheduled package change check: {str(e)}")
        return f"Error: {str(e)}"