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
        logger.info(f"YandexCloudWithProcessingStorage._save() called: name={name}")
        
        # Создаем полный путь к временному файлу
        temp_path = os.path.join(self._temp_dir, name)
        temp_dir = os.path.dirname(temp_path)
        os.makedirs(temp_dir, exist_ok=True)
        
        processed_path = None
        files_to_delete = set()  # Используем set для избежания дубликатов
        
        try:
            logger.info(f"Saving file to temp path: {temp_path}")
            # Сохраняем исходный файл во временное хранилище
            with open(temp_path, 'wb+') as temp_file:
                for chunk in content.chunks():
                    temp_file.write(chunk)
            
            logger.info(f"Calling _process_file for: {name}")
            # Вызываем обработку файла (переопределяется в подклассах)
            processed_path, additional_files = self._process_file(temp_path, name)
            logger.info(f"_process_file returned: processed_path={processed_path}, additional_files={additional_files}")

            # Добавляем файлы в список на удаление
            # processed_path всегда нужно удалить после загрузки
            files_to_delete.add(os.path.normpath(processed_path))
            for f in additional_files:
                if f:
                    files_to_delete.add(os.path.normpath(f))

            # Создаем копию для загрузки (чтобы избежать блокировки файла)
            import shutil
            upload_path = os.path.normpath(f"{processed_path}.upload")
            logger.info(f"Creating upload copy: {upload_path}")
            shutil.copy2(processed_path, upload_path)
            files_to_delete.add(upload_path)

            logger.info(f"Uploading to Yandex Cloud: {name}")
            # Загружаем обработанный файл в Yandex Cloud
            with open(upload_path, 'rb') as processed_file:
                # Используем стандартный метод загрузки YandexObjectStorage
                result = super()._save(name, processed_file)
                logger.info(f"Upload successful, result={result}")
                return result
            
        except Exception as e:
            logger.error(f"Ошибка при сохранении файла {name}: {e}", exc_info=True)
            raise
        finally:
            logger.info(f"Finally block: deleting {len(files_to_delete)} files")
            # Удаляем все временные файлы
            for file_path in files_to_delete:
                if file_path:
                    # Нормализуем путь для Windows
                    normalized_path = os.path.normpath(file_path)
                    logger.debug(f"Checking file for deletion: {normalized_path}, exists={os.path.exists(normalized_path)}")
                    if os.path.exists(normalized_path):
                        try:
                            # На Windows могут быть проблемы с блокировкой файлов
                            # Пробуем убедиться, что файл не используется
                            os.remove(normalized_path)
                            # Проверяем, действительно ли файл удалён
                            if os.path.exists(normalized_path):
                                logger.error(f"Файл не был удалён, несмотря на отсутствие ошибок: {normalized_path}")
                            else:
                                logger.info(f"Удалён временный файл: {normalized_path}")
                        except PermissionError as e:
                            logger.error(f"PermissionError при удалении {normalized_path}: {e}", exc_info=True)
                        except OSError as e:
                            logger.error(f"OSError при удалении {normalized_path}: {e}", exc_info=True)
                        except Exception as e:
                            logger.error(f"Неожиданная ошибка при удалении {normalized_path}: {e}", exc_info=True)
                    else:
                        logger.warning(f"Файл не найден для удаления: {normalized_path}")

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
