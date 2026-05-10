from django.contrib.auth import get_user_model
from core.models import Event, Ticket
from django.utils import timezone
import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'activity.settings')
django.setup()
User = get_user_model()

# Создаем пользователя-организатора
organizer, created = User.objects.get_or_create(
    username="testorganizer",
    defaults={
        "email": "organizer@example.com",
        "first_name": "Test",
        "last_name": "Organizer",
        "user_type": "partner",
    }
)
if created:
    organizer.set_password("testpass123")
    organizer.save()

# Создаем мероприятие
event, created = Event.objects.get_or_create(
    id=1,
    defaults={
        "title": "Test Event",
        "organizer": organizer,
        "date_time": timezone.now() + timezone.timedelta(days=7),
        "status": "active",
        "auto_close_sales_hours": 0,
        "allow_booking_without_payment": False,
        "description_short": "Test description",
        "description_full": "Test description full"
    }
)

# Создаем билет
ticket, created = Ticket.objects.get_or_create(
    id=1,
    event=event,
    defaults={
        "name": "Standard Ticket",
        "price": 100.00,
        "available_quantity": 1
    }
)

print(f"Создано мероприятие с ID: {event.id}")
print(f"Создан билет с ID: {ticket.id}, доступное количество: {ticket.available_quantity}")