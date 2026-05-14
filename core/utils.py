from django.utils import timezone
from django.db.models import Sum, F, DecimalField
from django.db.models.functions import Coalesce
from core.models import Order, Event, PayoutRequest
import os
from django.core.files import File
from PIL import Image, ImageDraw, ImageFont
import cv2
import numpy as np
from moviepy import VideoFileClip, TextClip, CompositeVideoClip
from moviepy.video.io.ImageSequenceClip import ImageSequenceClip
from io import BytesIO


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

    # Рассчитываем общие суммы
    total_sales = orders.aggregate(
        total=Coalesce(Sum("total_price"), 0, output_field=DecimalField())
    )["total"]

    total_commission = orders.aggregate(
        total=Coalesce(Sum("platform_commission"), 0, output_field=DecimalField())
    )["total"]

    # Рассчитываем сумму возвратов: учитываем заказы, которые были оплачены, но потом отменены
    refunded_orders = Order.objects.filter(
        ticket__event__in=partner_events,
        created_at__gte=start_date,
        created_at__lte=end_date,
        is_paid=True,
        payment_status="canceled",
    )

    total_refunds = refunded_orders.aggregate(
        total=Coalesce(Sum("total_price"), 0, output_field=DecimalField())
    )["total"]

    # Чистая сумма к выплате
    net_amount = total_sales - total_commission - total_refunds

    return {
        "total_sales": total_sales,
        "total_commission": total_commission,
        "total_refunds": total_refunds,
        "net_amount": net_amount,
        "orders": orders,
        "start_date": start_date,
        "end_date": end_date,
    }


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
        base_image = Image.open(input_image_path).convert("RGBA")
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

        return True
    except Exception as e:
        print(f"Ошибка при добавлении водяного знака на изображение: {e}")
        return False


def add_watermark_to_video(
    input_video_path,
    watermark_image_path,
    output_video_path=None,
    position=(1, 1),
    opacity=0.7,
):
    """
    Добавляет водяной знак (логотип) на видео.

    Args:
        input_video_path: путь к исходному видео.
        watermark_image_path: путь к изображению водяного знака.
        output_video_path: путь для сохранения результата. Если None, перезаписывает исходное видео.
        position: позиция водяного знака (1, 1) - правый нижний угол.
        opacity: прозрачность водяного знака (0.0 - 1.0).
    """
    try:
        # Загружаем видео
        video_clip = VideoFileClip(input_video_path)

        # Проверяем существование водяного знака
        if not os.path.exists(watermark_image_path):
            print(f"Файл водяного знака не найден: {watermark_image_path}")
            return False

        watermark = Image.open(watermark_image_path).convert("RGBA")

        # Изменяем размер водяного знака
        video_width, video_height = video_clip.size
        watermark.thumbnail((video_width // 4, video_height // 4))

        # Конвертируем водяной знак в формат, подходящий для moviepy
        watermark_np = np.array(watermark)
        watermark_np = cv2.cvtColor(watermark_np, cv2.COLOR_RGBA2BGRA)

        # Не используем TextClip, так как он вызывает конфликт с аргументом font
        # Водяной знак добавляется через make_frame

        # Используем функцию для наложения изображения
        def make_frame(t):
            frame = video_clip.get_frame(t).copy()
            h, w = frame.shape[:2]

            # Позиционируем водяной знак
            if position == (1, 1):  # Правый нижний угол
                x = w - watermark.width - 10
                y = h - watermark.height - 10
            else:
                x, y = position

            # Накладываем водяной знак
            overlay = frame.copy()
            overlay[y : y + watermark.height, x : x + watermark.width] = watermark_np[
                :, :, :3
            ]
            alpha = watermark_np[:, :, 3] / 255.0
            for c in range(3):  # Обрабатываем только RGB-каналы
                frame[y : y + watermark.height, x : x + watermark.width, c] = (
                    alpha * watermark_np[:, :, c]
                    + (1 - alpha)
                    * frame[y : y + watermark.height, x : x + watermark.width, c]
                )

            return frame

        # Создаём новый клип из обработанных кадров
        def frame_generator():
            for t in np.arange(0, video_clip.duration, 1.0 / video_clip.fps):
                yield make_frame(t)

        final_clip = ImageSequenceClip(list(frame_generator()), fps=video_clip.fps)
        final_clip.audio = video_clip.audio

        # Сохраняем результат
        try:
            output_path = output_video_path if output_video_path else input_video_path

            # Нормализуем путь для Windows
            output_path = os.path.normpath(output_path)
            output_path = output_path.replace("\\", "/")

            final_clip.write_videofile(
                output_path,
                codec="libx264",
                audio_codec="aac",
                threads=4,
                preset="fast",
                ffmpeg_params=[
                    "-pix_fmt",
                    "yuv420p",  # Для лучшей совместимости
                    "-movflags",
                    "+faststart",  # Для потокового воспроизведения
                ],
            )
        except Exception as e:
            print(f"Ошибка при сохранении видео с водяным знаком: {str(e)}")
            return False

        video_clip.close()
        final_clip.close()

        return True
    except Exception as e:
        print(f"Ошибка при добавлении водяного знака на видео: {e}")
        return False
