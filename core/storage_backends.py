"""
Кастомные хранилища для работы с Yandex Object Storage с предварительной обработкой файлов.
Yandex Object Storage совместим с S3, поэтому используем S3Boto3Storage.
"""

from django.conf import settings
from storages.backends.s3boto3 import S3Boto3Storage
import os
import tempfile
import logging

logger = logging.getLogger(__name__)


class YandexCloudWithProcessingStorage(S3Boto3Storage):
    """
    Кастомное хранилище для Yandex Object Storage с предварительной обработкой файлов.
    
    Файлы сначала сохраняются во временную директорию на сервере,
    затем обрабатываются и загружаются в Yandex Cloud.
    """
    
    def __init__(self, *args, **kwargs):
        # Настройки для Yandex Object Storage
        # Эти настройки берутся из settings.py, но можно переопределить здесь
        super().__init__(*args, **kwargs)
        
        self._temp_dir = getattr(settings, 'MEDIA_TEMP_DIR', os.path.join(settings.BASE_DIR, 'media_temp'))
        os.makedirs(self._temp_dir, exist_ok=True)
    
    def _save(self, name, content):
        """
        Сохраняет файл с предварительной обработкой.
        
        1. Сохраняет содержимое во временный файл на сервере
        2. Вызывает обработку (переопределяется в подклассах)
        3. Загружает обработанный файл в Yandex Cloud
        4. Удаляет временные файлы
        """
        # Создаем полный путь к временному файлу
        temp_path = os.path.join(self._temp_dir, name)
        temp_dir = os.path.dirname(temp_path)
        os.makedirs(temp_dir, exist_ok=True)
        
        processed_path = None
        files_to_delete = []  # Список файлов для удаления
        
        try:
            # Сохраняем исходный файл во временное хранилище
            with open(temp_path, 'wb+') as temp_file:
                for chunk in content.chunks():
                    temp_file.write(chunk)
            
            # Вызываем обработку файла (переопределяется в подклассах)
            processed_path, additional_files = self._process_file(temp_path, name)

            # Добавляем файлы в список на удаление
            files_to_delete = [temp_path, processed_path] + additional_files

            # Создаем копию для загрузки (чтобы избежать блокировки файла)
            import shutil
            upload_path = processed_path + '.upload'
            shutil.copy2(processed_path, upload_path)
            files_to_delete.append(upload_path)

            # Загружаем обработанный файл в Yandex Cloud
            with open(upload_path, 'rb') as processed_file:
                # Используем стандартный метод загрузки YandexObjectStorage
                return super()._save(name, processed_file)
            
        except Exception as e:
            logger.error(f"Ошибка при сохранении файла {name}: {e}")
            raise
        finally:
            # Удаляем все временные файлы
            for file_path in files_to_delete:
                if file_path and os.path.exists(file_path):
                    try:
                        os.remove(file_path)
                    except OSError as e:
                        logger.warning(f"Не удалось удалить временный файл {file_path}: {e}")

            # Очищаем пустые директории
            self._cleanup_empty_dirs(temp_dir)
    
    def _process_file(self, temp_path, name):
        """
        Обрабатывает файл перед загрузкой в облако.
        По умолчанию - ничего не делает. Переопределите в подклассах.
        
        Args:
            temp_path: путь к временному файлу на сервере
            name: имя файла (путь в хранилище)
            
        Returns:
            tuple: (путь к обработанному файлу, список дополнительных файлов для удаления)
        """
        return temp_path, []
    
    def _cleanup_empty_dirs(self, dir_path):
        """Удаляет пустые директории."""
        while dir_path and dir_path != self._temp_dir:
            try:
                if os.path.isdir(dir_path) and not os.listdir(dir_path):
                    os.rmdir(dir_path)
                    dir_path = os.path.dirname(dir_path)
                else:
                    break
            except OSError:
                break
    
    def get_available_name(self, name, max_length=None):
        """Возвращает доступное имя файла."""
        return super().get_available_name(name, max_length)
    
    def exists(self, name):
        """Проверяет существование файла в облаке."""
        return super().exists(name)
    
    def url(self, name):
        """Возвращает публичный URL файла."""
        return super().url(name)
