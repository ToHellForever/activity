from django.apps import AppConfig
from django.conf import settings


class CoreConfig(AppConfig):
    name = "core"

    def ready(self):
        # Импортируем сигналы, чтобы они зарегистрировались
        import core.signals
        # Импортируем proxy-модели
        import core.proxy_models

        # Применяем кастомные хранилища при использовании Yandex Cloud
        self.apply_storage_backends()
    
    def apply_storage_backends(self):
        """
        Применяет кастомные хранилища к моделям при использовании Yandex Cloud.
        """
        # Применяем хранилища только если включен Yandex Cloud
        if not getattr(settings, 'USE_YANDEX_CLOUD', False):
            return
            
        try:
            # Проверяем доступность модуля storages
            import storages
        except ImportError:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(
                "Модуль 'storages' не найден. Установите его: pip install django-storages"
            )
            return
        
        try:
            from .image_storage import YandexImageProcessingStorage
            from .video_storage import YandexVideoProcessingStorage
            from .document_storage import YandexDocumentProcessingStorage
            from .models import Event, EventImage
            
            # Применяем хранилище к полю image модели Event
            Event._meta.get_field('image').storage = YandexImageProcessingStorage()
            
            # Применяем хранилище к полю document модели EventImage
            Event._meta.get_field('program_file').storage = YandexDocumentProcessingStorage()
            
            # Применяем хранилище к полю video_url модели Event
            Event._meta.get_field('video_url').storage = YandexVideoProcessingStorage()
            
            # Применяем хранилище к полю image модели EventImage
            EventImage._meta.get_field('image').storage = YandexImageProcessingStorage()
            
        except ImportError as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Не удалось загрузить кастомные хранилища: {e}")
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Ошибка при применении хранилищ: {e}")

