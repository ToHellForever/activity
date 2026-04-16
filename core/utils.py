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

    # Получаем текущий файл из поля
    current_file_field = getattr(instance, field_name)

    # Если уже есть файл, удаляем его перед заменой
    if current_file_field:
        current_file_field.delete(save=False)

    # Открываем сжатый файл и сохраняем его в указанное поле
    with open(compressed_path, "rb") as f:
        django_file = File(f)
        current_file_field.save(name, django_file, save=False)
