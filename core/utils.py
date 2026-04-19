"""
Утилиты для работы с файлами и водяными знаками.
"""

import os
from django.core.files import File
from PIL import Image, ImageDraw, ImageFont
import cv2
import numpy as np
from moviepy import VideoFileClip, TextClip, CompositeVideoClip
from io import BytesIO


def add_watermark_to_image(input_image_path, watermark_image_path, output_image_path=None, position=(1, 1), opacity=0.3):
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
            position = (base_width - watermark.width - 10, base_height - watermark.height - 10)
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


def add_watermark_to_video(input_video_path, watermark_image_path, output_video_path=None, position=(1, 1), opacity=0.7):
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
        watermark = Image.open(watermark_image_path).convert("RGBA")

        # Изменяем размер водяного знака
        video_width, video_height = video_clip.size
        watermark.thumbnail((video_width // 4, video_height // 4))

        # Конвертируем водяной знак в формат, подходящий для moviepy
        watermark_np = np.array(watermark)
        watermark_np = cv2.cvtColor(watermark_np, cv2.COLOR_RGBA2BGRA)

        # Создаем клип для водяного знака
        watermark_clip = (
            TextClip("", fontsize=1, color="white", transparent=True)
            .set_duration(video_clip.duration)
            .set_position(lambda t: position)
        )

        # Используем функцию для наложения изображения
        def make_frame(t):
            frame = video_clip.get_frame(t)
            h, w = frame.shape[:2]

            # Позиционируем водяной знак
            if position == (1, 1):  # Правый нижний угол
                x = w - watermark.width - 10
                y = h - watermark.height - 10
            else:
                x, y = position

            # Накладываем водяной знак
            overlay = frame.copy()
            overlay[y:y + watermark.height, x:x + watermark.width] = watermark_np[:, :, :3]
            alpha = watermark_np[:, :, 3] / 255.0
            frame[y:y + watermark.height, x:x + watermark.width] = (
                alpha * watermark_np[:, :, :3] + (1 - alpha) * frame[y:y + watermark.height, x:x + watermark.width]
            )

            return frame

        # Создаем финальное видео
        final_clip = video_clip.fl(make_frame)

        # Сохраняем результат
        if output_video_path:
            final_clip.write_videofile(output_video_path, codec="libx264", audio_codec="aac")
        else:
            final_clip.write_videofile(input_video_path, codec="libx264", audio_codec="aac")

        video_clip.close()
        final_clip.close()

        return True
    except Exception as e:
        print(f"Ошибка при добавлении водяного знака на видео: {e}")
        return False
