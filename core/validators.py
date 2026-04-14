"""
Валидаторы для моделей и форм.
"""

from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
import os
import tempfile
import shutil
from moviepy import VideoFileClip
from core.utils import compress_and_replace_video_field


def compress_video(input_path, output_path):
    """
    Максимальное сжатие видео для тестирования с исправленными параметрами.
    """
    clip = VideoFileClip(input_path)

    original_size = os.path.getsize(input_path) / (1024 * 1024)  # в МБ
    duration = clip.duration
    width, height = clip.size

    print(
        f"DEBUG: Original video - Size: {original_size:.2f}MB, Duration: {duration:.1f}s, Resolution: {width}x{height}"
    )
    # Вычисляем целевое разрешение, сохраняя соотношение сторон
    aspect_ratio = width / height
    target_width = 1280
    target_height = int(target_width / aspect_ratio)

    print(f"DEBUG: Target resolution: {target_width}x{target_height}")

    clip.write_videofile(
        output_path,
        codec="libx264",
        audio_codec="aac",
        bitrate="800k",
        threads=4,
        preset="veryfast",
        ffmpeg_params=[
            "-crf",
            "30",
            "-movflags",
            "faststart",
            "-pix_fmt",
            "yuv420p",
            "-vf",
            f"scale={target_width}:{target_height}:force_original_aspect_ratio=decrease",
        ],
    )
    clip.close()

    compressed_size = os.path.getsize(output_path) / (1024 * 1024)
    print(f"DEBUG: Compressed video size: {compressed_size:.2f}MB")
    print(f"DEBUG: Compression ratio: {compressed_size/original_size:.1%}")

    return output_path


def validate_and_compress_video(value):
    """
    Валидатор для проверки длительности видео и его сжатия.
    """
    if not value:
        return

    try:
        # Проверяем наличие файла (на случай, если поле не обязательное)
        if not hasattr(value, "file") or not value.file:
            return

        # Сбрасываем указатель файла на начало перед проверкой длительности
        value.file.seek(0)

        # --- ШАГ 1: Проверка длительности ---
        # Используем контекстный менеджер для автоматического закрытия клипа
        with VideoFileClip(
            value.file.temporary_file_path()
            if hasattr(value.file, "temporary_file_path")
            else value.file.temporary_file_path()
        ) as clip:
            duration = clip.duration

            if duration > 300:
                raise ValidationError(
                    _(
                        "Длительность видео не должна превышать 5 минут (текущая: %d секунд)."
                    )
                    % int(duration)
                )

        # --- ШАГ 2: Сжатие и замена файла ---
        # Сбрасываем указатель файла на начало перед сжатием
        value.file.seek(0)

        # Создаем временный файл для сжатого видео
        with tempfile.NamedTemporaryFile(
            suffix=".mp4", delete=False
        ) as temp_compressed:
            temp_compressed_path = temp_compressed.name

        try:
            # Сбрасываем указатель файла на начало перед сжатием
            value.file.seek(0)
            # Сжимаем видео
            compressed_path = compress_video(
                value.file.temporary_file_path(), temp_compressed_path
            )
            # Сохраняем путь к сжатому видео во временном атрибуте экземпляра модели
            # Это позволит корректно сохранить файл при вызове model.save()
            from django.core.files.uploadedfile import TemporaryUploadedFile

            if isinstance(value.instance, TemporaryUploadedFile):
                # Если это TemporaryUploadedFile, сохраняем путь в экземпляре модели
                value.instance._compressed_path = compressed_path
            else:
                # Иначе используем стандартную логику
                from core.utils import compress_and_replace_video_field

                compress_and_replace_video_field(value.instance, compressed_path)
        finally:
            # Удаляем временный файл
            if os.path.exists(temp_compressed_path):
                os.unlink(temp_compressed_path)

    except ValidationError:
        # Пробрасываем ошибку валидации дальше
        raise
    except Exception as e:
        # Ловим все остальные ошибки (IOError, проблемы с ffmpeg и т.д.)
        raise ValidationError(_("Ошибка при обработке видео: %s") % str(e))
