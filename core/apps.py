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
            from .models import Event, EventImage, PartnerDocument
            from partner_app.models import PartnerProfile
            
            # Применяем хранилище к полю image модели Event
            Event._meta.get_field('image').storage = YandexImageProcessingStorage()
            
            # Применяем хранилище к полю document модели EventImage
            Event._meta.get_field('program_file').storage = YandexDocumentProcessingStorage()
            
            # Применяем хранилище к полю video_url модели Event
            Event._meta.get_field('video_url').storage = YandexVideoProcessingStorage()
            
            # Применяем хранилище к полю image модели EventImage
            EventImage._meta.get_field('image').storage = YandexImageProcessingStorage()
            
            # Применяем хранилище к полю document модели PartnerDocument
            PartnerDocument._meta.get_field('document').storage = YandexDocumentProcessingStorage()
            
            # Применяем хранилище к полю logo модели PartnerProfile
            PartnerProfile._meta.get_field('logo').storage = YandexImageProcessingStorage()
            
        except ImportError as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Не удалось загрузить кастомные хранилища: {e}")
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Ошибка при применении хранилищ: {e}")

        # Применяем хранилище к модели SalesReport из partner_app
        try:
            from .document_storage import YandexDocumentProcessingStorage
            from partner_app.models import SalesReport

            SalesReport._meta.get_field('file_path').storage = YandexDocumentProcessingStorage()
        except ImportError as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Не удалось загрузить хранилище для SalesReport: {e}")
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Ошибка при применении хранилища для SalesReport: {e}")

