"""
Хранилище для видео с обработкой перед загрузкой в Yandex Cloud.
Видео сохраняется в локальное временное хранилище и обрабатывается асинхронно через Celery.
"""
from django.conf import settings
from django.core.files.storage import FileSystemStorage
import os
import logging
import uuid

logger = logging.getLogger(__name__)


class YandexVideoProcessingStorage(FileSystemStorage):
    """
    Хранилище для видео:
    - Сохраняет видео в локальное временное хранилище (media_temp)
    - Обработка (сжатие + водяной знак) происходит асинхронно через Celery
    - После обработки видео загружается в Яндекс Cloud
    """
    
    def __init__(self, *args, **kwargs):
        # Настраиваем хранилище для временной директории
        temp_dir = getattr(settings, 'MEDIA_TEMP_DIR', os.path.join(settings.BASE_DIR, 'media_temp'))
        super().__init__(location=temp_dir, base_url=None)
    
    def _process_file(self, temp_path, name):
        """
        Сохраняет видео во временное хранилище и возвращает путь.
        Обработка (сжатие + водяной знак) происходит в Celery задаче.
        После обработки видео загружается в Яндекс Cloud через storage_backends.
        
        Args:
            temp_path: путь к временному файлу на сервере
            name: имя файла (путь в хранилище)
            
        Returns:
            tuple: (путь к файлу, список дополнительных файлов для удаления)
        """
        # Генерируем уникальное имя файла для избежания конфликтов
        ext = os.path.splitext(name)[1]
        unique_name = f"{uuid.uuid4().hex}{ext}"
        unique_path = os.path.join(self.location, 'event_videos', unique_name)
        
        # Создаем директорию если нет
        os.makedirs(os.path.dirname(unique_path), exist_ok=True)
        
        # Копируем файл во временное хранилище
        import shutil
        shutil.copy2(temp_path, unique_path)
        
        logger.info(f"Video storage: saved to temp storage at {unique_path}, will be processed by Celery")
        
        # Возвращаем относительный путь (хранится в БД)
        relative_path = os.path.join('event_videos', unique_name)
        return unique_path, [temp_path]  # temp_path можно удалить
