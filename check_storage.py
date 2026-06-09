"""
Скрипт для диагностики настроек хранилищ.
"""

import os
import sys
import django

# Настройка Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'activity.settings')
django.setup()

from django.conf import settings
from core.models import Event, EventImage

print("=" * 60)
print("ДИАГНОСТИКА ХРАНИЛИЩ")
print("=" * 60)

# 1. Проверка настроек
print("\n1. Настройки:")
print(f"   USE_YANDEX_CLOUD: {settings.USE_YANDEX_CLOUD}")
print(f"   DEFAULT_FILE_STORAGE: {settings.DEFAULT_FILE_STORAGE}")
print(f"   MEDIA_ROOT: {settings.MEDIA_ROOT}")
print(f"   MEDIA_TEMP_DIR: {settings.MEDIA_TEMP_DIR}")
print(f"   WATERMARK_PATH: {settings.WATERMARK_PATH}")

# Проверка ключей Yandex Cloud
if settings.USE_YANDEX_CLOUD:
    print(f"\n   Ключи Yandex Cloud:")
    print(f"   AWS_ACCESS_KEY_ID: {'Установлен' if settings.AWS_ACCESS_KEY_ID else 'НЕ УСТАНОВЛЕН'}")
    print(f"   AWS_SECRET_ACCESS_KEY: {'Установлен' if settings.AWS_SECRET_ACCESS_KEY else 'НЕ УСТАНОВЛЕН'}")
    print(f"   AWS_STORAGE_BUCKET_NAME: {settings.AWS_STORAGE_BUCKET_NAME}")
    print(f"   AWS_S3_ENDPOINT_URL: {settings.AWS_S3_ENDPOINT_URL}")

# 2. Проверка водяного знака
print("\n2. Водяной знак:")
watermark_exists = os.path.exists(settings.WATERMARK_PATH)
print(f"   Существует: {watermark_exists}")
if watermark_exists:
    print(f"   Размер: {os.path.getsize(settings.WATERMARK_PATH)} байт")

# 3. Проверка хранилищ моделей
print("\n3. Хранилища моделей:")
event_image_storage = Event._meta.get_field('image').storage
print(f"   Event.image.storage: {type(event_image_storage).__name__}")

event_video_storage = Event._meta.get_field('video_url').storage
print(f"   Event.video_url.storage: {type(event_video_storage).__name__}")

event_image_storage = EventImage._meta.get_field('image').storage
print(f"   EventImage.image.storage: {type(event_image_storage).__name__}")

# 4. Проверка последнего мероприятия
print("\n4. Последнее мероприятие:")
try:
    event = Event.objects.latest('id')
    print(f"   ID: {event.id}")
    print(f"   Название: {event.title}")
    print(f"   Изображение: {event.image}")
    
    if event.image:
        print(f"   URL: {event.image.url}")
        print(f"   Существует в облаке: {event.image.storage.exists(event.image.name) if hasattr(event.image.storage, 'exists') else 'N/A'}")
        # path не работает с S3-совместимыми хранилищами
        # print(f"   Путь: {event.image.path}")
    else:
        print("   Изображение: None")
    
    # Проверка дополнительных фото
    images = EventImage.objects.filter(event=event)
    print(f"   Дополнительных фото: {images.count()}")
    
    for img in images:
        print(f"     - Фото {img.id}: {img.image}")
        if img.image:
            print(f"       URL: {img.image.url}")
            # path не работает с S3-совместимыми хранилищами
            # print(f"       Путь: {img.image.path}")
            
except Event.DoesNotExist:
    print("   Мероприятий нет")

# 5. Проверка папок
print("\n5. Папки:")
media_root = settings.MEDIA_ROOT
print(f"   MEDIA_ROOT: {media_root}")
print(f"   Существует: {os.path.exists(media_root)}")

if os.path.exists(media_root):
    event_images_dir = os.path.join(media_root, 'event_images')
    print(f"   event_images/: {os.path.exists(event_images_dir)}")
    
    media_temp_dir = settings.MEDIA_TEMP_DIR
    print(f"   media_temp/: {os.path.exists(media_temp_dir)}")

# 6. Рекомендации
print("\n6. Рекомендации:")
if not settings.USE_YANDEX_CLOUD:
    print("   ⚠️  USE_YANDEX_CLOUD=False - файлы загружаются локально")
    print("   💡 Для Yandex Cloud установите USE_YANDEX_CLOUD=True в .env")

if not watermark_exists:
    print("   ⚠️  Водяной знак не найден")
    print("   💡 Положите watermark.png в media/")

if settings.USE_YANDEX_CLOUD:
    if not settings.AWS_ACCESS_KEY_ID or not settings.AWS_SECRET_ACCESS_KEY:
        print("   ⚠️  Ключи AWS не установлены!")
        print("   💡 Добавьте YANDEX_CLOUD_ACCESS_KEY_ID и YANDEX_CLOUD_SECRET_ACCESS_KEY в .env")
    if not settings.AWS_STORAGE_BUCKET_NAME:
        print("   ⚠️  Имя бакета не указано!")
        print("   💡 Добавьте YANDEX_CLOUD_BUCKET_NAME в .env")

print("\n" + "=" * 60)