"""
Хранилище для изображений с обработкой перед загрузкой в Yandex Cloud.
"""

from .storage_backends import YandexCloudWithProcessingStorage
from django.conf import settings
import os
from PIL import Image
import logging

logger = logging.getLogger(__name__)


class YandexImageProcessingStorage(YandexCloudWithProcessingStorage):
    """
    Хранилище для изображений с обработкой:
    - Изменение размера до 800x600
    - Сжатие с качеством 85%
    - Добавление водяного знака
    """
    
    def _process_file(self, temp_path, name):
        """
        Обрабатывает изображение перед загрузкой.
        
        Args:
            temp_path: путь к временному файлу на сервере
            name: имя файла (путь в хранилище)
            
        Returns:
            tuple: (путь к обработанному файлу, список дополнительных файлов для удаления)
        """
        try:
            # Открываем изображение
            image = Image.open(temp_path)
            
            # Конвертируем в RGB если нужно (для PNG с прозрачностью)
            if image.mode in ('RGBA', 'P', 'LA'):
                background = Image.new('RGB', image.size, (255, 255, 255))
                if image.mode == 'RGBA':
                    background.paste(image, mask=image.split()[-1])
                elif image.mode == 'LA':
                    background.paste(image, mask=image.split()[-1])
                else:
                    background.paste(image)
                image = background
            elif image.mode != 'RGB':
                image = image.convert('RGB')
            
            # Изменяем размер до 800x600
            max_size = (800, 600)
            if image.size[0] > max_size[0] or image.size[1] > max_size[1]:
                image.thumbnail(max_size, Image.Resampling.LANCZOS)
            
            # Путь для обработанного файла
            base_name = os.path.splitext(temp_path)[0]
            ext = os.path.splitext(temp_path)[1].lower()
            
            # Всегда сохраняем как JPEG для лучшего сжатия
            if ext in ['.jpg', '.jpeg']:
                processed_path = temp_path
            else:
                processed_path = f"{base_name}_processed.jpg"
            
            # Сохраняем с сжатием
            image.save(processed_path, 'JPEG', quality=85, optimize=True)
            
            # Добавляем водяной знак если файл существует
            watermark_path = getattr(settings, 'WATERMARK_PATH', 
                                   os.path.join(settings.MEDIA_ROOT, 'watermark.png'))
            
            if os.path.exists(watermark_path):
                try:
                    watermark_output = processed_path.replace('.jpg', '_watermarked.jpg')
                    
                    if self._add_watermark(processed_path, watermark_path, watermark_output):
                        # Возвращаем путь к файлу с водяным знаком и список файлов для удаления
                        # processed_path нужно удалить, так как watermark_output - это финальный файл
                        return watermark_output, [processed_path]
                    else:
                        logger.warning(f"Не удалось добавить водяной знак к изображению: {name}")
                        return processed_path, []

                except Exception as e:
                    logger.error(f"Ошибка при добавлении водяного знака: {e}")
                    return processed_path, []

            return processed_path, []

        except Exception as e:
            # При ошибке возвращаем исходный файл
            logger.error(f"Ошибка при обработке изображения {name}: {e}")
            return temp_path, []
    
    def _add_watermark(self, input_path, watermark_path, output_path):
        """
        Добавляет водяной знак к изображению.
        
        Args:
            input_path: путь к входному изображению
            watermark_path: путь к водяному знаку
            output_path: путь для сохранения результата
            
        Returns:
            bool: True если успешно, False в случае ошибки
        """
        try:
            # Открываем изображение
            base_image = Image.open(input_path).convert("RGBA")
            watermark = Image.open(watermark_path).convert("RGBA")
            
            # Изменяем размер водяного знака пропорционально
            base_width, base_height = base_image.size
            watermark.thumbnail((base_width // 4, base_height // 4))
            
            # Создаем прозрачный слой для водяного знака
            watermark_layer = Image.new("RGBA", base_image.size, (0, 0, 0, 0))
            
            # Позиционируем в правом нижнем углу
            position = (
                base_width - watermark.width - 10,
                base_height - watermark.height - 10
            )
            
            watermark_layer.paste(watermark, position, watermark)
            
            # Накладываем водяной знак с прозрачностью 0.3
            watermarked_image = Image.alpha_composite(base_image, watermark_layer)
            watermarked_image = watermarked_image.convert("RGB")
            
            # Сохраняем результат
            watermarked_image.save(output_path, 'JPEG', quality=85, optimize=True)
            
            return True
            
        except Exception as e:
            logger.error(f"Ошибка при добавлении водяного знака: {e}")
            return False
