import os
from celery import Celery
from celery.schedules import crontab

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'activity.settings')

app = Celery('activity')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

# Настройка периодических задач
app.conf.beat_schedule = {
    'close-event-sales-every-hour': {
        'task': 'core.tasks.close_event_sales',
        'schedule': crontab(minute=0),  # Запускать каждый час
    },
}
