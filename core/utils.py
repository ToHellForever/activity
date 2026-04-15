"""
Утилиты для работы с файлами.
"""

import os
from django.core.files import File


def compress_and_replace_video_field(instance, compressed_path, field_name="video_url"):
    """
    Сохраняет сжатое видео в указанное поле экземпляра модели.

    Args:
        instance: экземпляр модели
        compressed_path: путь к сжатому файлу
        field_name: имя поля, в которое нужно сохранить видео (по умолчанию video_url)
    """
    # Определяем имя файла
    name = os.path.basename(compressed_path)

    # Открываем сжатый файл и сохраняем его в указанное поле
    with open(compressed_path, "rb") as f:
        django_file = File(f)
        getattr(instance, field_name).save(name, django_file, save=False)
