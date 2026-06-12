from django.utils import timezone
from django.db.models import Sum, F, DecimalField
from django.db.models.functions import Coalesce
import os
from django.core.files import File
from PIL import Image, ImageDraw, ImageFont
import cv2
import numpy as np
from moviepy import VideoFileClip
from moviepy.video.VideoClip import ImageClip
from moviepy.video.compositing.CompositeVideoClip import CompositeVideoClip
from io import BytesIO
import logging


def generate_sales_register(partner, start_date, end_date):
    """
    Формирует реестр продаж для партнёра за указанный период.

    Args:
        partner: Объект пользователя (CustomUser), для которого формируется реестр.
        start_date: Начальная дата периода (datetime).
        end_date: Конечная дата периода (datetime).

    Returns:
        dict: Словарь с данными реестра:
            - total_sales: Общая сумма продаж (без учёта комиссии).
            - total_commission: Общая сумма удержанной комиссии.
            - total_refunds: Общая сумма возвратов.
            - net_amount: Чистая сумма к выплате (total_sales - total_commission - total_refunds).
            - orders: Список заказов с детализацией.
    """
    # Импортируем модели локально, чтобы избежать циклического импорта
    from core.models import Order, Event, PayoutRequest

    # Получаем все мероприятия партнёра
    partner_events = Event.objects.filter(organizer=partner)

    # Получаем все заказы для этих мероприятий за указанный период
    # Включаем все оплаченные заказы (включая отменённые) для детализации
    orders = Order.objects.filter(
        ticket__event__in=partner_events,
        created_at__gte=start_date,
        created_at__lte=end_date,
        is_paid=True,
    ).select_related("ticket__event")

    # Рассчитываем общие суммы (исключаем возвраты из выручки и комиссии)
    non_refunded_orders = orders.exclude(payment_status__in=["canceled", "refunded"])

    total_sales = non_refunded_orders.aggregate(
        total=Coalesce(Sum("total_price"), 0, output_field=DecimalField())
    )["total"]

    total_commission = non_refunded_orders.aggregate(
        total=Coalesce(Sum("platform_commission"), 0, output_field=DecimalField())
    )["total"]

    # Рассчитываем сумму возвратов: учитываем заказы, которые были оплачены, но потом возвращены или отменены
    refunded_orders = Order.objects.filter(
        ticket__event__in=partner_events,
        created_at__gte=start_date,
        created_at__lte=end_date,
        is_paid=True,
        payment_status__in=["canceled", "refunded"],
    )

    total_refunds = refunded_orders.aggregate(
        total=Coalesce(Sum("total_price"), 0, output_field=DecimalField())
    )["total"]

    # Чистая сумма к выплате (возвраты уже исключены из выручки и комиссии)
    net_amount = total_sales - total_commission

    return {
        "total_sales": total_sales,
        "total_commission": total_commission,
        "total_refunds": total_refunds,
        "net_amount": net_amount,
        "orders": orders,
        "start_date": start_date,
        "end_date": end_date,
    }


def resize_image_to_800px(input_image_path, output_image_path=None):
    """
    Приводит изображение к размеру 800x800 пикселей.

    Args:
        input_image_path: путь к исходному изображению.
        output_image_path: путь для сохранения результата. Если None, перезаписывает исходное изображение.

    Returns:
        bool: True, если операция прошла успешно, False в случае ошибки.
    """
    try:
        image = Image.open(input_image_path)
        image = image.resize((800, 600), Image.LANCZOS)

        if output_image_path:
            image.save(output_image_path)
        else:
            image.save(input_image_path)

        return True
    except Exception as e:
        print(f"Ошибка при изменении размера изображения: {e}")
        return False

def add_watermark_to_image(
    input_image_path,
    watermark_image_path,
    output_image_path=None,
    position=(1, 1),
    opacity=0.3,
):
    """
    Добавляет водяной знак (логотип) на изображение.

    Args:
        input_image_path: путь к исходному изображению.
        watermark_image_path: путь к изображению водяного знака.
        output_image_path: путь для сохранения результата. Если None, перезаписывает исходное изображение.
        position: позиция водяного знака (1, 1) - правый нижний угол.
        opacity: прозрачность водяного знака (0.0 - 1.0).
    """
    try:
        # Приводим изображение к размеру 800x800 пикселей
        temp_image_path = "temp_resized_image.png"
        resize_image_to_800px(input_image_path, temp_image_path)

        base_image = Image.open(temp_image_path).convert("RGBA")
        watermark = Image.open(watermark_image_path).convert("RGBA")

        # Изменяем размер водяного знака пропорционально
        base_width, base_height = base_image.size
        watermark.thumbnail((base_width // 4, base_height // 4))

        # Создаем прозрачный слой для водяного знака
        watermark_layer = Image.new("RGBA", base_image.size, (0, 0, 0, 0))
        if position == (1, 1):  # Правый нижний угол
            position = (
                base_width - watermark.width - 10,
                base_height - watermark.height - 10,
            )
        watermark_layer.paste(watermark, position, watermark)

        # Накладываем водяной знак с заданной прозрачностью
        watermarked_image = Image.alpha_composite(base_image, watermark_layer)
        watermarked_image = watermarked_image.convert("RGB")

        # Сохраняем результат
        if output_image_path:
            watermarked_image.save(output_image_path)
        else:
            watermarked_image.save(input_image_path)

        # Удаляем временный файл
        os.remove(temp_image_path)

        return True
    except Exception as e:
        print(f"Ошибка при добавлении водяного знака на изображение: {e}")
        return False


def compress_image(
    input_image_path,
    output_image_path=None,
    quality=85,
    max_size=(800, 600),
):
    """
    Сжимает изображение с заданным качеством и максимальным размером.

    Args:
        input_image_path: путь к исходному изображению.
        output_image_path: путь для сохранения результата. Если None, перезаписывает исходное изображение.
        quality: качество сжатия (0-100). По умолчанию 85.
        max_size: максимальный размер изображения (ширина, высота). По умолчанию (800, 600).
    """
    try:
        image = Image.open(input_image_path)

        # Изменяем размер, если изображение больше заданного
        if image.size[0] > max_size[0] or image.size[1] > max_size[1]:
            image.thumbnail(max_size, Image.LANCZOS)

        # Сохраняем с заданным качеством
        if output_image_path:
            image.save(output_image_path, quality=quality, optimize=True)
        else:
            image.save(input_image_path, quality=quality, optimize=True)

        return True
    except Exception as e:
        print(f"Ошибка при сжатии изображения: {e}")
        return False


def compress_video(input_video_path, output_video_path):
    """
    Сжимает видео с помощью FFmpeg напрямую (быстрее MoviePy).
    
    Args:
        input_video_path: путь к входному видео
        output_video_path: путь для сохранения сжатого видео
        
    Returns:
        bool: True если успешно, False в случае ошибки
    """
    logger = logging.getLogger(__name__)
    logger.info(f"compress_video: input={input_video_path}, output={output_video_path}")
    
    # Проверяем что файл существует и не пустой
    if not os.path.exists(input_video_path):
        logger.error(f"compress_video: Input file does not exist: {input_video_path}")
        return False
    
    input_size = os.path.getsize(input_video_path)
    if input_size == 0:
        logger.error(f"compress_video: Input file is empty: {input_video_path}")
        return False
    
    logger.info(f"compress_video: Input file size: {input_size} bytes")
    
    try:
        import subprocess
        
        # Устанавливаем параметры для скорости:
        # -preset ultrafast - максимально быстрое сжатие
        # -crf 28 - компромисс качество/размер (чем больше, тем меньше файл)
        # -threads 0 - автовыбор количества потоков
        # -vf scale=-2:720 - уменьшить высоту до 720p (ширина авто)
        cmd = [
            'ffmpeg', '-y', '-i', input_video_path,
            '-c:v', 'libx264',
            '-preset', 'ultrafast',  # максимально быстро
            '-crf', '28',  # качество (23-28 - хороший баланс)
            '-vf', 'scale=-2:720',  # уменьшить до 720p по высоте
            '-c:a', 'aac',
            '-b:a', '128k',
            '-threads', '0',  # автовыбор
            '-movflags', '+faststart',
            output_video_path
        ]
        
        logger.info(f"compress_video: Running FFmpeg command")
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=3600  # 1 час максимум
        )
        
        if result.returncode != 0:
            logger.error(f"compress_video: FFmpeg error: {result.stderr}")
            return False
            
        # Проверяем что файл создан и имеет размер
        if os.path.exists(output_video_path):
            output_size = os.path.getsize(output_video_path)
            logger.info(f"compress_video: Output file size: {output_size} bytes "
                       f"({output_size/input_size*100:.1f}% of original)")
            if output_size > 0:
                logger.info(f"compress_video: Successfully compressed to {output_video_path}")
                return True
            else:
                logger.error(f"compress_video: Output file is empty: {output_video_path}")
                return False
        else:
            logger.error(f"compress_video: Output file was not created: {output_video_path}")
            return False
            
    except subprocess.TimeoutExpired:
        logger.error(f"compress_video: Timeout - video too long")
        return False
    except FileNotFoundError:
        logger.error(f"compress_video: FFmpeg not found. Install FFmpeg first.")
        return False
    except Exception as e:
        logger.error(f"compress_video: Error - {e}", exc_info=True)
        return False


def add_watermark_to_video(
    input_video_path,
    watermark_image_path,
    output_video_path=None,
    position=(1, 1),
    opacity=0.3,
):
    """
    Добавляет водяной знак с помощью FFmpeg (быстрее MoviePy).
    
    Args:
        input_video_path: путь к исходному видео.
        watermark_image_path: путь к изображению водяного знака.
        output_video_path: путь для сохранения результата.
        position: позиция водяного знака (1, 1) - правый нижний угол.
        opacity: прозрачность водяного знака (0.0 - 1.0).

    Returns:
        bool: True, если операция прошла успешно, False в случае ошибки.
    """
    logger = logging.getLogger(__name__)
    logger.info(f"add_watermark_to_video: input={input_video_path}, output={output_video_path}")
    
    try:
        import subprocess
        import tempfile
        
        # Создаем временный файл с прозрачным водяным знаком
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
            temp_watermark_path = tmp.name
        
        # Изменяем размер и прозрачность водяного знака
        watermark_cmd = [
            'ffmpeg', '-y', '-i', watermark_image_path,
            '-vf', f'fps=1,scale=iw:{opacity}',  # 1 fps, установить альфа-канал
            temp_watermark_path
        ]
        
        # Простой вариант - просто накладываем водяной знак с прозрачностью через overlay filter
        output_path = output_video_path or input_video_path
        
        # FFmpeg filter для водяного знака:
        # - alphaifnot=0 - добавить альфа-канал если нет
        # - format=yuva420p - формат с альфа-каналом
        # - scale - уменьшить размер
        # - overlay=x:y - позиционирование
        filter_complex = (
            f"[1:v]format=yuva420p,scale=iw/4:-1[wm];"
            f"[0:v][wm]overlay=main_w-overlay_w-10:main_h-overlay_h-10:alpha=1[v]"
        )

        cmd = [
            'ffmpeg', '-y', '-i', input_video_path,
            '-i', watermark_image_path,
            '-filter_complex', filter_complex,
            '-map', '[v]',
            '-map', '0:a?',  # аудио из оригинала
            '-c:v', 'libx264',
            '-preset', 'ultrafast',
            '-crf', '28',
            '-c:a', 'aac',
            '-b:a', '128k',
            '-threads', '0',
            '-movflags', '+faststart',
            output_path
        ]
        
        logger.info(f"add_watermark_to_video: Running FFmpeg command")
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=3600
        )
        
        # Удаляем временный файл
        try:
            if os.path.exists(temp_watermark_path):
                os.remove(temp_watermark_path)
        except:
            pass

        if result.returncode != 0:
            logger.error(f"add_watermark_to_video: FFmpeg error: {result.stderr}")
            return False
        
        if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            logger.info(f"add_watermark_to_video: Successfully added watermark to {output_path}")
            return True
        else:
            logger.error(f"add_watermark_to_video: Output file is empty or not created")
            return False
            
    except subprocess.TimeoutExpired:
        logger.error(f"add_watermark_to_video: Timeout")
        return False
    except FileNotFoundError:
        logger.error(f"add_watermark_to_video: FFmpeg not found")
        return False
    except Exception as e:
        logger.error(f"add_watermark_to_video: Error - {e}", exc_info=True)
        return False

