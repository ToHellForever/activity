# core/video_storage.py
from django.conf import settings
from django.core.files.storage import FileSystemStorage
from .storage_backends import YandexCloudWithProcessingStorage
import os
import logging
import uuid

logger = logging.getLogger(__name__)


class YandexVideoProcessingStorage(FileSystemStorage):
    """
    Хранилище для видео с двухэтапной обработкой:
    1. Сохраняет видео локально в media_temp для обработки
    2. После обработки Celery задачей видео загружается в Yandex Cloud
    3. .url() возвращает Yandex Cloud URL, а не локальный
    """
    
    def __init__(self, *args, **kwargs):
        # Получаем subdirectory из kwargs или используем 'event_videos' по умолчанию
        self.subdirectory = kwargs.pop('subdirectory', 'event_videos')
        temp_dir = getattr(settings, 'MEDIA_TEMP_DIR', os.path.join(settings.BASE_DIR, 'media_temp'))
        super().__init__(location=temp_dir, base_url=None)
        
        # Создаём Yandex Cloud хранилище для получения URL после загрузки
        if getattr(settings, 'USE_YANDEX_CLOUD', False):
            self.cloud_storage = YandexCloudWithProcessingStorage()
        else:
            self.cloud_storage = None
    
    def url(self, name):
        """
        Возвращает Yandex Cloud URL если видео загружено в облако,
        иначе локальный URL.
        """
        if self.cloud_storage and settings.USE_YANDEX_CLOUD:
            # Проверяем существует ли файл в облаке
            try:
                if self.cloud_storage.exists(name):
                    return self.cloud_storage.url(name)
            except Exception:
                pass
        # Локальный URL для необработанных видео
        return super().url(name)
    
    def _process_file(self, temp_path, name):
        """
        Сохраняет видео во временное хранилище для последующей обработки.
        """
        ext = os.path.splitext(name)[1]
        unique_name = f"{uuid.uuid4().hex}{ext}"
        unique_path = os.path.join(self.location, self.subdirectory, unique_name)
        
        os.makedirs(os.path.dirname(unique_path), exist_ok=True)
        
        import shutil
        shutil.copy2(temp_path, unique_path)
        
        logger.info(f"Video storage: saved to temp storage at {unique_path}")
        
        relative_path = os.path.join(self.subdirectory, unique_name)
        return unique_path, [temp_path]