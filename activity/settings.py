from dotenv import load_dotenv
import os

from pathlib import Path

load_dotenv()
# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/6.0/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.getenv("SECRET_KEY")

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = ['bus-monitor-product-enter.trycloudflare.com', 'localhost', '127.0.0.1']

# Application definition

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "taggit",
    "visitor_app",
    "partner_app",
    "venues",
    "core",
    "payment",
    'storages',
    "imagekit",
    "django_celery_beat",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "activity.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
        "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "core.context_processors.admin_quick_links",
            ],
        },
    },
]

WSGI_APPLICATION = "activity.wsgi.application"

# Database
# https://docs.djangoproject.com/en/6.0/ref/settings/#databases

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": "activity_db",
        "USER": "postgres",
        "PASSWORD": "Dima228anosov",
        "HOST": "localhost",
        "PORT": "5432",
    }
}

AUTH_USER_MODEL = "core.CustomUser"

LOGIN_URL = "login/"
LOGIN_REDIRECT_URL = "/"

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]
AUTHENTICATION_BACKENDS = [
    "core.backends.EmailBackend",
    "django.contrib.auth.backends.ModelBackend",
]
LANGUAGE_CODE = "ru"

TIME_ZONE = "UTC"

USE_I18N = True

USE_TZ = True

CRONJOBS = [
    ('*/5 * * * *', 'django.core.management.call_command', ['clean_expired_reservations']),
]

STATIC_URL = "static/"

STATICFILES_DIRS = [
    os.path.join(BASE_DIR, 'static'),
]

USE_YANDEX_CLOUD = os.getenv('USE_YANDEX_CLOUD', 'False').lower() == 'true'

# Путь к водяному знаку
WATERMARK_PATH = os.path.join(BASE_DIR, 'media', 'watermark.png')

# Временная директория для обработки файлов
MEDIA_TEMP_DIR = os.path.join(BASE_DIR, 'media_temp')

if USE_YANDEX_CLOUD:
    # Используем кастомные хранилища с обработкой
    DEFAULT_FILE_STORAGE = 'core.storage_backends.YandexCloudWithProcessingStorage'
    
    # Специальные хранилища для разных типов файлов
    EVENT_IMAGE_STORAGE = 'core.image_storage.YandexImageProcessingStorage'
    EVENT_VIDEO_STORAGE = 'core.video_storage.YandexVideoProcessingStorage'
    EVENT_DOCUMENT_STORAGE = 'core.document_storage.YandexDocumentProcessingStorage'
    VENUE_IMAGE_STORAGE = 'core.image_storage.YandexImageProcessingStorage'
    VENUE_VIDEO_STORAGE = 'core.video_storage.YandexVideoProcessingStorage'
    # Настройки Yandex Object Storage (S3-совместимый)
    AWS_ACCESS_KEY_ID = os.getenv('YANDEX_CLOUD_ACCESS_KEY_ID')
    AWS_SECRET_ACCESS_KEY = os.getenv('YANDEX_CLOUD_SECRET_ACCESS_KEY')
    AWS_STORAGE_BUCKET_NAME = os.getenv('YANDEX_CLOUD_BUCKET_NAME')
    AWS_S3_ENDPOINT_URL = os.getenv('YANDEX_CLOUD_ENDPOINT_URL', 'https://storage.yandexcloud.net')
    AWS_S3_REGION_NAME = 'ru-central1'
    AWS_S3_FILE_OVERWRITE = False
    AWS_DEFAULT_ACL = None  # Yandex Cloud не требует ACL
    
    # CDN URL для изображений (опционально)
    YANDEX_CLOUD_CDN_URL = os.getenv('YANDEX_CLOUD_CDN_URL', '')
    
    # Отключаем локальное хранение медиа в продакшене (опционально)
    MEDIA_ROOT = '' 
else:
    # Локальное хранилище для разработки
    DEFAULT_FILE_STORAGE = 'django.core.files.storage.FileSystemStorage'

    # Для локального режима тоже создаем медиа-директорию
    MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

CELERY_BROKER_URL = "redis://localhost:6379/0"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = os.getenv("EMAIL_HOST")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
EMAIL_USE_TLS = os.getenv("EMAIL_USE_TLS", "True") == "True"
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD")
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL")

# Настройка логирования
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "file": {
            "level": "DEBUG",
            "class": "logging.FileHandler",
            "filename": os.path.join(BASE_DIR, "debug.log"),
        },
    },
    "loggers": {
        "core": {
            "handlers": ["file"],
            "level": "DEBUG",
        },
        "venues": { 
            "handlers": ["file"],
            "level": "DEBUG",
        },
        "visitor_app": {
            "handlers": ["file"],
            "level": "DEBUG",
        },
        "ticket_purchase": {
            "handlers": ["file"],
            "level": "DEBUG",
        },
        "payment": {
            "handlers": ["file"],
            "level": "DEBUG",
        },
    },
}

# Redis Configuration
REDIS_CONFIG = {
    "host": "localhost",
    "port": 6379,
    "db": 0,
    "socket_timeout": 5,
    "socket_connect_timeout": 2,
}

# Celery Configuration
CELERY_BROKER_URL = "redis://localhost:6379/0"
CELERY_RESULT_BACKEND = "redis://localhost:6379/0"
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = "Europe/Moscow"
CELERY_BEAT_SCHEDULE = {
    "check-race-conditions-hourly": {
        "task": "core.tasks.check_race_conditions_task",
        "schedule": 3600.0,
    },
    "check-unpaid-tickets-every-10-minutes": {
        "task": "core.tasks.check_unpaid_tickets",
        "schedule": 1000.0,
    },
    "check-reserved-tickets-every-10-minutes": {
        "task": "core.tasks.check_reserved_tickets",
        "schedule": 1000.0,
    },
    "send-scheduled-reports-every-12-hours": {
        "task": "partner_app.tasks.send_scheduled_reports",
        "schedule": 43200.0,
    },
    "check-scheduled-package-changes-hourly": {
        "task": "core.tasks.check_and_apply_scheduled_package_changes",
        "schedule": 3600.0,
    },
}
YOOKASSA_SHOP_ID = os.getenv("YOOKASSA_SHOP_ID")
YOOKASSA_SECRET_KEY = os.getenv("YOOKASSA_SECRET_KEY")
YOOKASSA_WEBHOOK_KEY = os.getenv("YOOKASSA_WEBHOOK_KEY")

USE_L10N = True
LANGUAGE_CODE = 'ru-ru'
