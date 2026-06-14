from django.apps import AppConfig
from django.conf import settings

class VenuesConfig(AppConfig):
    name = 'venues'
    
    def ready(self):
        import venues.signals
        
        # Применяем хранилища только если включен Yandex Cloud
        if not getattr(settings, 'USE_YANDEX_CLOUD', False):
            return
        
        try:
            from core.image_storage import YandexImageProcessingStorage
            from core.video_storage import YandexVideoProcessingStorage
            
            # Применяем хранилище к полю image модели VenueImage
            from venues.models import VenueImage
            VenueImage._meta.get_field('image').storage = YandexImageProcessingStorage()
            
            # Применяем хранилище к полю video модели Venue
            from venues.models import Venue
            Venue._meta.get_field('video').storage = YandexVideoProcessingStorage()
            
        except ImportError as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Не удалось применить хранилища: {e}")
