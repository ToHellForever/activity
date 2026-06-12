"""
Тестовый скрипт для проверки обработки видео через Celery.
Запускается: python test_video_processing.py
"""
import os
import sys
import django

# Добавляем корень проекта в PATH
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Настраиваем Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'activity.settings')
django.setup()

import shutil
from core.models import Event
from core.tasks import process_video_task
from django.contrib.auth import get_user_model

User = get_user_model()

def find_test_video():
    """Ищет тестовое видео"""
    # Фиксированный путь к тестовому видео
    fixed_path = r'C:\Users\diman\Downloads\Green-Screen-Glitch-Grunge-Overlay-Effect-Layer.mp4'
    if os.path.exists(fixed_path):
        return fixed_path
    
    return None

def main():
    print("=" * 60)
    print("Тест обработки видео через Celery")
    print("=" * 60)
    
    # 1. Находим тестовое видео
    video_path = find_test_video()
    if not video_path:
        print("\n❌ Тестовое видео не найдено в media_temp/event_videos/")
        print("Пожалуйста, создайте мероприятие через веб-интерфейс хотя бы один раз.")
        return
    
    print(f"\n✓ Найдено видео: {video_path}")
    print(f"  Размер: {os.path.getsize(video_path) / (1024*1024):.2f} MB")
    
    # 2. Создаём тестового пользователя (если нет)
    user, created = User.objects.get_or_create(
        username='test_organizer',
        defaults={
            'email': 'test@example.com',
            'is_active': True,
            'first_name': 'Test',
            'last_name': 'Organizer'
        }
    )
    if created:
        user.set_password('password123')
        user.save()
        print(f"\n✓ Создан тестовый пользователь: {user.username}")
    else:
        print(f"\n✓ Найден тестовый пользователь: {user.username}")
    
    # 3. Создаём тестовое мероприятие
    from core.models import EventPackage
    from django.utils import timezone
    from datetime import timedelta
    
    # Находим или создаем пакет
    package, _ = EventPackage.objects.get_or_create(
        name='Test Package',
        defaults={
            'price': 0,
            'max_photos': 20,
        }
    )
    
    # Создаем мероприятие с видео
    from django.core.files import File
    
    event_data = {
        'organizer': user,
        'title': f'Test Event {timezone.now().strftime("%Y%m%d_%H%M%S")}',
        'description_short': 'Тестовое мероприятие для проверки обработки видео',
        'description_full': 'Это тестовое мероприятие для проверки работы Celery при обработке видео.',
        'date_time': timezone.now() + timedelta(days=7),
        'status': 'active',
        'package': package,
    }
    
    event = Event.objects.create(**event_data)
    print(f"\n✓ Создано мероприятие: {event.title} (ID: {event.id})")
    
    # Копируем видео в поле video_url
    with open(video_path, 'rb') as f:
        event.video_url.save(
            os.path.basename(video_path),
            File(f),
            save=True
        )
    
    print(f"✓ Видео загружено: {event.video_url.name}")
    print(f"  Хэш до обработки: {event.processed_video_url_hash}")
    
    # 4. Запускаем задачу Celery
    print("\n" + "=" * 60)
    print("Запуск задачи Celery для обработки видео...")
    print("=" * 60)
    
    result = process_video_task.delay(
        model_name='Event',
        instance_id=event.id,
        video_field_name='video_url',
        hash_field_name='processed_video_url_hash'
    )
    
    print(f"✓ Задача отправлена в очередь: {result.id}")
    print("\n⏳ Ожидаем выполнения задачи (проверьте консоль Celery worker)...")
    
    # 5. Ждем выполнения (для solo pool это происходит синхронно)
    try:
        # Ждем до 60 секунд
        output = result.get(timeout=60)
        print(f"\n✓ Результат задачи: {output}")
        
        # 6. Проверяем результат
        event.refresh_from_db()
        print(f"\n{'=' * 60}")
        print("Итоги:")
        print(f"{'=' * 60}")
        print(f"Мероприятие: {event.title} (ID: {event.id})")
        print(f"Видео: {event.video_url.name}")
        print(f"Хэш после обработки: {event.processed_video_url_hash}")
        
        if event.processed_video_url_hash:
            print("\n✅ УСПЕХ! Видео обработано успешно!")
        else:
            print("\n⚠️  Внимание: хэш не обновлён, проверьте логи Celery")
            
    except Exception as e:
        print(f"\n❌ Ошибка при выполнении задачи: {e}")
        print("Проверьте логи Celery worker для деталей.")
    
    # 7. Очищаем тестовые данные (опционально)
    print("\n" + "=" * 60)
    print("Очистка тестовых данных...")
    print("=" * 60)
    
    delete_input = input("Удалить тестовое мероприятие? (y/n): ").strip().lower()
    if delete_input == 'y':
        # Удаляем файлы
        if event.video_url:
            event.video_url.delete()
        event.delete()
        print("✓ Тестовое мероприятие удалено")
    else:
        print(f"ℹ️  Мероприятие сохранено (ID: {event.id})")
    
    print("\nТест завершён!")

if __name__ == '__main__':
    main()
