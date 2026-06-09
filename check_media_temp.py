"""
Скрипт для проверки и очистки папки media_temp
"""

import os
import shutil
from django.conf import settings

# Настройка Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'activity.settings')

import django
django.setup()

def check_media_temp():
    """Проверяет содержимое папки media_temp"""
    media_temp = settings.MEDIA_TEMP_DIR

    if not os.path.exists(media_temp):
        print(f"✅ Папка {media_temp} не существует (это нормально)")
        return

    print(f"\n📁 Проверка папки: {media_temp}")
    print("=" * 60)

    # Рекурсивно считаем файлы и папки
    total_files = 0
    total_size = 0
    files_info = []

    for root, dirs, files in os.walk(media_temp):
        for file in files:
            file_path = os.path.join(root, file)
            file_size = os.path.getsize(file_path)
            total_files += 1
            total_size += file_size

            # Относительный путь
            rel_path = os.path.relpath(file_path, media_temp)
            files_info.append((rel_path, file_size))

    if total_files == 0:
        print("✅ Папка пуста - все временные файлы удалены корректно!")
        return

    print(f"⚠️  Найдено {total_files} файлов, общий размер: {total_size / 1024:.2f} KB")
    print("\nФайлы:")
    for rel_path, size in files_info:
        size_str = f"{size} B" if size < 1024 else f"{size / 1024:.2f} KB"
        print(f"  • {rel_path} ({size_str})")

    print("\n" + "=" * 60)

    # Предлагаем очистку
    response = input("\n❓ Очистить папку media_temp? (y/n): ").strip().lower()

    if response == 'y' or response == 'да':
        try:
            shutil.rmtree(media_temp)
            os.makedirs(media_temp, exist_ok=True)
            print(f"✅ Папка {media_temp} очищена!")
        except Exception as e:
            print(f"❌ Ошибка при очистке: {e}")
    else:
        print("📝 Очистка отменена")

if __name__ == "__main__":
    check_media_temp()