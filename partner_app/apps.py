from django.apps import AppConfig
from django.conf import settings


class PartnerAppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'partner_app'

    def ready(self):
        # Применяем хранилища только если включен Yandex Cloud
        if not getattr(settings, 'USE_YANDEX_CLOUD', False):
            return
        
        try:
            from core.image_storage import YandexImageProcessingStorage
            from core.video_storage import YandexVideoProcessingStorage
            
            # Применяем хранилище к полю logo модели PartnerProfile
            from partner_app.models import PartnerProfile
            PartnerProfile._meta.get_field('logo').storage = YandexImageProcessingStorage()
            
            # Применяем хранилище к полю video_business_card модели PartnerProfile
            # Указываем subdirectory='partner_video' для отдельного хранения
            PartnerProfile._meta.get_field('video_business_card').storage = YandexVideoProcessingStorage(
                subdirectory='partner_video'
            )
            
        except ImportError as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Не удалось применить хранилища для partner_app: {e}")
