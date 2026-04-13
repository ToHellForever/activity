from celery import shared_task
from core.models import Event
import os
from moviepy import VideoFileClip

@shared_task
def process_event_video(event_id):
    try:
        event = Event.objects.get(id=event_id)
        
        if event.video_url:
            input_path = event.video_url.path  # Путь к файлу на сервере
            output_dir = os.path.dirname(input_path)
            output_path = os.path.join(output_dir, "compressed_" + os.path.basename(input_path))
            
            # Открываем видео для анализа и обработки
            clip = VideoFileClip(input_path)
            
            # Проверка длительности (5 минут = 300 секунд)
            if clip.duration > 300: 
                clip.close()
                raise ValueError("Видео слишком длинное. Максимум 5 минут.")
            
            # Сжимаем видео
            clip.write_videofile(output_path, codec='libx264', bitrate='2500k')
            clip.close()
            
            # Заменяем файл в модели на сжатый
            with open(output_path, 'rb') as f:
                event.video_url.save(event.video_url.name, f, save=True)
            
            # Удаляем старый файл (необязательно)
            os.remove(input_path)
    except Exception as e:
        print(f"Ошибка обработки видео: {e}")