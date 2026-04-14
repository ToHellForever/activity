"""
Утилиты для работы с файлами.
"""

import os
from django.core.files import File


def compress_and_replace_video_field(instance, compressed_path):
    """
    Сохраняет сжатое видео в поле video_url экземпляра модели.

    Args:
        instance: экземпляр модели
        compressed_path: путь к сжатому файлу
    """
    # Определяем имя файла
    name = os.path.basename(compressed_path)

    # Открываем сжатый файл и сохраняем его в поле video_url
    with open(compressed_path, "rb") as f:
        django_file = File(f)
        instance.video_url.save(name, django_file, save=False)
