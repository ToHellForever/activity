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
            
            # Применяем хранилище к полю image модели PortfolioImage
            from partner_app.models import PortfolioImage
            PortfolioImage._meta.get_field('image').storage = YandexImageProcessingStorage()
            
            # Применяем хранилище к полю new_video_url модели EventChangeRequest
            # Это нужно, чтобы видео сохранялось локально для обработки Celery-задачей.
            # Если использовать YandexCloudWithProcessingStorage (default), файл загружается
            # в облако и локальная копия удаляется — Celery-задача не может найти файл.
            from partner_app.models import EventChangeRequest
            EventChangeRequest._meta.get_field('new_video_url').storage = YandexVideoProcessingStorage(
                subdirectory='change_request_videos'
            )
            
        except ImportError as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Не удалось применить хранилища для partner_app: {e}")
