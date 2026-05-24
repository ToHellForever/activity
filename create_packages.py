from django.core.wsgi import get_wsgi_application
import os

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'activity.settings')
application = get_wsgi_application()

from core.models import EventPackage

# Создаем пакет "Старт"
start_package, _ = EventPackage.objects.get_or_create(
    name="Старт",
    defaults={
        "max_active_events": 1,
        "event_card_type": "basic",
        "description_type": "short",
        "has_program_and_speakers": True,
        "max_photos": 1,
        "has_video": False,
        "has_platform_request": True,
        "has_free_registration": True,
        "has_ticket_sales": True,
        "visibility_level": "basic",
        "has_collection_participation": False,
    }
)

# Создаем пакет "Оптимум"
optimum_package, _ = EventPackage.objects.get_or_create(
    name="Оптимум",
    defaults={
        "max_active_events": 3,
        "event_card_type": "extended",
        "description_type": "detailed",
        "has_program_and_speakers": True,
        "max_photos": 5,
        "has_video": False,
        "has_platform_request": True,
        "has_free_registration": True,
        "has_ticket_sales": True,
        "visibility_level": "enhanced",
        "has_collection_participation": True,
    }
)

# Создаем пакет "Приоритет"
priority_package, _ = EventPackage.objects.get_or_create(
    name="Приоритет",
    defaults={
        "max_active_events": 10,
        "event_card_type": "priority",
        "description_type": "detailed",
        "has_program_and_speakers": True,
        "max_photos": 10,
        "has_video": True,
        "has_platform_request": True,
        "has_free_registration": True,
        "has_ticket_sales": True,
        "visibility_level": "priority",
        "has_collection_participation": True,
    }
)

print("Стандартные пакеты созданы.")