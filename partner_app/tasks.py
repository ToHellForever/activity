from celery import shared_task
from core.models import Event
import os
from moviepy import VideoFileClip

@shared_task
def process_event_video(event_id):
    try:
        event = Event.objects.get(id=event_id)
        
        if event.video_url:
            input_path = event.video_url.path # Путь к файлу на сервере
            output_path = os.path.join(os.path.dirname(input_path), "compressed_" + os.path.basename(input_path))
            
            clip = VideoFileClip(input_path)
            clip.write_videofile(output_path, codec='libx264', bitrate='2500k')
            clip.close()
            
            # Заменяем файл в модели на сжатый
            with open(output_path, 'rb') as f:
                event.video_url.save(event.video_url.name, f, save=True)
            
            # Удаляем старый файл (необязательно)
            os.remove(input_path)
    except Exception as e:
        print(f"Ошибка обработки видео: {e}")