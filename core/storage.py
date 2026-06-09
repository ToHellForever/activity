"""
Модуль для кастомных хранилищ.
"""

from django.conf import settings

# Импортируем хранилища только если они нужны
try:
    from .storage_backends import YandexCloudWithProcessingStorage
    from .image_storage import YandexImageProcessingStorage
    from .video_storage import YandexVideoProcessingStorage
except ImportError:
    YandexCloudWithProcessingStorage = None
    YandexImageProcessingStorage = None
    YandexVideoProcessingStorage = None


def get_image_storage():
    """Возвращает хранилище для изображений."""
    if settings.USE_YANDEX_CLOUD and YandexImageProcessingStorage:
        return YandexImageProcessingStorage()
    return None


def get_video_storage():
    """Возвращает хранилище для видео."""
    if settings.USE_YANDEX_CLOUD and YandexVideoProcessingStorage:
        return YandexVideoProcessingStorage()
    return None
