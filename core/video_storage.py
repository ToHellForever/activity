"""
Хранилище для видео с обработкой перед загрузкой в Yandex Cloud.
"""

from .storage_backends import YandexCloudWithProcessingStorage
from django.conf import settings
import os
import logging

logger = logging.getLogger(__name__)


class YandexVideoProcessingStorage(YandexCloudWithProcessingStorage):
    """
    Хранилище для видео с обработкой:
    - Сжатие видео
    - Добавление водяного знака
    """
    
    def _process_file(self, temp_path, name):
        """
        Обрабатывает видео перед загрузкой.
        
        Args:
            temp_path: путь к временному файлу на сервере
            name: имя файла (путь в хранилище)
            
        Returns:
            tuple: (путь к обработанному файлу, список дополнительных файлов для удаления)
        """
        try:
            # Сжимаем видео
            compressed_path = temp_path.replace('.tmp', '_compressed.mp4')
            
            if not self._compress_video(temp_path, compressed_path):
                logger.error(f"Ошибка при сжатии видео: {temp_path}")
                return temp_path, []

            # Добавляем водяной знак
            watermark_path = getattr(settings, 'WATERMARK_PATH',
                os.path.join(settings.MEDIA_ROOT, 'watermark.png'))
            
            if not os.path.exists(watermark_path):
                logger.error(f"Файл водяного знака не найден: {watermark_path}")
                # Возвращаем сжатое видео как итоговое, temp_path нужно удалить
                return compressed_path, [temp_path]

            watermarked_path = temp_path.replace('.tmp', '_watermarked.mp4')
            
            if not self._add_watermark(compressed_path, watermark_path, watermarked_path):
                logger.error(f"Ошибка при добавлении водяного знака: {compressed_path}")
                # Возвращаем сжатое видео как итоговое, temp_path нужно удалить
                return compressed_path, [temp_path]

            # Возвращаем путь к файлу с водяным знаком и список файлов для удаления
            # temp_path и compressed_path нужно удалить, watermarked_path останется
            return watermarked_path, [temp_path, compressed_path]

        except Exception as e:
            logger.error(f"Ошибка при обработке видео {name}: {e}")
            # При ошибке возвращаем исходный файл
            return temp_path, []
    
    def _compress_video(self, input_path, output_path):
        """
        Сжимает видео.
        
        Args:
            input_path: путь к входному видео
            output_path: путь для сохранения результата
            
        Returns:
            bool: True если успешно, False в случае ошибки
        """
        try:
            from moviepy import VideoFileClip
            
            # Загружаем видео
            clip = VideoFileClip(input_path)
            
            # Устанавливаем параметры сжатия
            # Битрейт видео: 2500k (хорошее качество для веб)
            # Битрейт аудио: 128k
            clip.write_videofile(
                output_path,
                codec='libx264',
                audio_codec='aac',
                bitrate='2500k',
                audio_bitrate='128k',
                threads=4,
                preset='fast',
                ffmpeg_params=[
                    '-pix_fmt', 'yuv420p',
                    '-movflags', '+faststart'
                ]
            )
            
            clip.close()
            
            # Проверяем что файл создан и имеет размер
            if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                return True
            else:
                return False
                
        except Exception as e:
            logger.error(f"Ошибка при сжатии видео: {e}")
            return False
    
    def _add_watermark(self, input_path, watermark_path, output_path):
        """
        Добавляет водяной знак к видео.
        
        Args:
            input_path: путь к входному видео
            watermark_path: путь к водяному знаку
            output_path: путь для сохранения результата
            
        Returns:
            bool: True если успешно, False в случае ошибки
        """
        try:
            from moviepy import VideoFileClip
            from moviepy.video.io.ImageSequenceClip import ImageSequenceClip
            import cv2
            import numpy as np
            
            # Загружаем видео
            video_clip = VideoFileClip(input_path)
            
            # Проверяем существование водяного знака
            if not os.path.exists(watermark_path):
                logger.error(f"Файл водяного знака не найден: {watermark_path}")
                return False
            
            watermark = Image.open(watermark_path).convert("RGBA")
            
            # Изменяем размер водяного знака
            video_width, video_height = video_clip.size
            watermark.thumbnail((video_width // 4, video_height // 4))
            
            # Конвертируем водяной знак в формат для moviepy
            watermark_np = np.array(watermark)
            watermark_np = cv2.cvtColor(watermark_np, cv2.COLOR_RGBA2BGRA)
            
            # Функция для наложения изображения
            def make_frame(t):
                frame = video_clip.get_frame(t).copy()
                h, w = frame.shape[:2]
                
                # Позиционируем водяной знак в правом нижнем углу
                x = w - watermark.width - 10
                y = h - watermark.height - 10
                
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
            final_clip.write_videofile(
                output_path,
                codec="libx264",
                audio_codec="aac",
                threads=4,
                preset="fast",
                ffmpeg_params=[
                    "-pix_fmt",
                    "yuv420p",
                    "-movflags",
                    "+faststart",
                ],
            )
            
            video_clip.close()
            final_clip.close()
            
            # Проверяем что файл создан и имеет размер
            if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                return True
            else:
                return False
            
        except Exception as e:
            logger.error(f"Ошибка при добавлении водяного знака на видео: {e}")
            return False
