# Инструкция по миграции между облачными S3-провайдерами

## Краткий ответ: **ДА, можно без потери данных**

Ваш проект уже спроектирован с учётом возможности смены провайдера:
- ✅ Использует S3-совместимые хранилища (boto3, django-storages)
- ✅ В БД хранятся только пути к файлам, не URL-адреса
- ✅ Все настройки через переменные окружения
- ✅ Код не зависит от конкретного провайдера

---

## 📋 Сравнение популярных S3-провайдеров

| Характеристика | Yandex Cloud | Selectel | Wasabi | AWS S3 |
|---------------|--------------|----------|--------|--------|
| S3 совместимость | ✅ Полная | ✅ Полная | ✅ Полная | ✅ Стандарт |
| Регионы в РФ | ✅ Москва | ✅ Москва/СПб | ❌ Нет | ❌ Нет |
| CDN | ✅ Встроен | ✅ Встроен | ✅ Встроен | ✅ CloudFront |
| Цена хранения (за ГБ/мес) | ~$0.023 | ~$0.012 | ~$0.0069 | $0.023 |
| Цена трафика | Низкая | Очень низкая | Безлимит | Высокая |
| Цена запросов | Средняя | Низкая | Безлимит | Средняя |

---

## 🔧 Подготовка к миграции

### Шаг 1: Создайте бакет у нового провайдера

**Selectel:**
1. Зарегистрируйтесь в [Selectel](https://selectel.ru/)
2. Создайте бакет в панели управления
3. Создайте Access Keys (в разделе "S3-хранилище" → "Ключи доступа")

**Wasabi:**
1. Зарегистрируйтесь в [Wasabi](https://wasabi.com/)
2. Создайте бакет
3. Создайте Access Keys

### Шаг 2: Настройте переменные окружения

**Текущая конфигурация (Yandex Cloud):**

```env
# .env (текущая)
USE_YANDEX_CLOUD=True
YANDEX_CLOUD_ACCESS_KEY_ID=ваш_access_key
YANDEX_CLOUD_SECRET_ACCESS_KEY=ваш_secret_key
YANDEX_CLOUD_BUCKET_NAME=ваш_бакет
YANDEX_CLOUD_ENDPOINT_URL=https://storage.yandexcloud.net
YANDEX_CLOUD_CDN_URL=https://ваш-акселератор.cloudflare.ru
```

**Новая конфигурация (Selectel):**

```env
# .env (для Selectel)
USE_YANDEX_CLOUD=False

# Selectel S3
SELECTEL_ACCESS_KEY_ID=ваш_selectel_key
SELECTEL_SECRET_ACCESS_KEY=ваш_selectel_secret
SELECTEL_BUCKET_NAME=ваш_бакет
SELECTEL_ENDPOINT_URL=https://s3.selcdn.ru
SELECTEL_REGION=ru-1
```

**Новая конфигурация (Wasabi):**

```env
# .env (для Wasabi)
USE_YANDEX_CLOUD=False

# Wasabi S3
WASABI_ACCESS_KEY_ID=ваш_wasabi_key
WASABI_SECRET_ACCESS_KEY=ваш_wasabi_secret
WASABI_BUCKET_NAME=ваш_бакет
WASABI_ENDPOINT_URL=https://s3.wasabisys.com
WASABI_REGION=eu-central-1
```

### Шаг 3: Обновите `activity/settings.py`

Добавьте блок для нового провайдера:

```python
# activity/settings.py

USE_YANDEX_CLOUD = os.getenv('USE_YANDEX_CLOUD', 'False').lower() == 'true'
USE_SELECTEL_CLOUD = os.getenv('USE_SELECTEL_CLOUD', 'False').lower() == 'true'
USE_WASABI_CLOUD = os.getenv('USE_WASABI_CLOUD', 'False').lower() == 'true'

if USE_YANDEX_CLOUD:
    DEFAULT_FILE_STORAGE = 'core.storage_backends.YandexCloudWithProcessingStorage'
    EVENT_IMAGE_STORAGE = 'core.image_storage.YandexImageProcessingStorage'
    EVENT_VIDEO_STORAGE = 'core.video_storage.YandexVideoProcessingStorage'
    
    AWS_ACCESS_KEY_ID = os.getenv('YANDEX_CLOUD_ACCESS_KEY_ID')
    AWS_SECRET_ACCESS_KEY = os.getenv('YANDEX_CLOUD_SECRET_ACCESS_KEY')
    AWS_STORAGE_BUCKET_NAME = os.getenv('YANDEX_CLOUD_BUCKET_NAME')
    AWS_S3_ENDPOINT_URL = os.getenv('YANDEX_CLOUD_ENDPOINT_URL', 'https://storage.yandexcloud.net')
    AWS_S3_REGION_NAME = 'ru-central1'

elif USE_SELECTEL_CLOUD:
    DEFAULT_FILE_STORAGE = 'core.storage_backends.YandexCloudWithProcessingStorage'
    EVENT_IMAGE_STORAGE = 'core.image_storage.YandexImageProcessingStorage'
    EVENT_VIDEO_STORAGE = 'core.video_storage.YandexVideoProcessingStorage'
    
    AWS_ACCESS_KEY_ID = os.getenv('SELECTEL_ACCESS_KEY_ID')
    AWS_SECRET_ACCESS_KEY = os.getenv('SELECTEL_SECRET_ACCESS_KEY')
    AWS_STORAGE_BUCKET_NAME = os.getenv('SELECTEL_BUCKET_NAME')
    AWS_S3_ENDPOINT_URL = os.getenv('SELECTEL_ENDPOINT_URL', 'https://s3.selcdn.ru')
    AWS_S3_REGION_NAME = os.getenv('SELECTEL_REGION', 'ru-1')

elif USE_WASABI_CLOUD:
    DEFAULT_FILE_STORAGE = 'core.storage_backends.YandexCloudWithProcessingStorage'
    EVENT_IMAGE_STORAGE = 'core.image_storage.YandexImageProcessingStorage'
    EVENT_VIDEO_STORAGE = 'core.video_storage.YandexVideoProcessingStorage'
    
    AWS_ACCESS_KEY_ID = os.getenv('WASABI_ACCESS_KEY_ID')
    AWS_SECRET_ACCESS_KEY = os.getenv('WASABI_SECRET_ACCESS_KEY')
    AWS_STORAGE_BUCKET_NAME = os.getenv('WASABI_BUCKET_NAME')
    AWS_S3_ENDPOINT_URL = os.getenv('WASABI_ENDPOINT_URL', 'https://s3.wasabisys.com')
    AWS_S3_REGION_NAME = os.getenv('WASABI_REGION', 'eu-central-1')

else:
    # Локальное хранилище для разработки
    DEFAULT_FILE_STORAGE = 'django.core.files.storage.FileSystemStorage'
    MEDIA_ROOT = os.path.join(BASE_DIR, 'media')
```

---

## 🚀 Миграция данных

### Способ 1: rclone (рекомендуется)

**Установка:**

```bash
# Windows (PowerShell)
# Скачайте с https://rclone.org/downloads/ и распакуйте
# Или через Chocolatey:
choco install rclone

# Linux
curl https://rclone.org/install.sh | sudo bash
```

**Настройка:**

```bash
# 1. Настройте Yandex Cloud
rclone config create yandex s3 \
  --s3-provider Other \
  --s3-endpoint https://storage.yandexcloud.net \
  --s3-access-key-id ВАШ_YANDEX_KEY \
  --s3-secret-access-key ВАШ_YANDEX_SECRET \
  --s3-region ru-central1

# 2. Настройте Selectel
rclone config create selectel s3 \
  --s3-provider Other \
  --s3-endpoint https://s3.selcdn.ru \
  --s3-access-key-id ВАШ_SELECTEL_KEY \
  --s3-secret-access-key ВАШ_SELECTEL_SECRET \
  --s3-region ru-1

# 3. Или Wasabi
rclone config create wasabi s3 \
  --s3-provider Wasabi \
  --s3-endpoint https://s3.wasabisys.com \
  --s3-access-key-id ВАШ_WASABI_KEY \
  --s3-secret-access-key ВАШ_WASABI_SECRET \
  --s3-region eu-central-1
```

**Синхронизация данных:**

```bash
# Dry-run (проверка без копирования)
rclone sync yandex:ваш-бакет selectel:ваш-бакet \
  --dry-run \
  --checksum \
  --progress \
  --verbose

# Реальная синхронизация
rclone sync yandex:ваш-бакет selectel:ваш-бакет \
  --checksum \
  --progress \
  --verbose

# Проверка после синхронизации
rclone check yandex:ваш-бакет selectel:ваш-бакет
```

**Параметры rclone:**
- `--checksum` - проверяет контрольные суммы файлов
- `--progress` - показывает прогресс
- `--verbose` - подробный лог
- `--dry-run` - тестовый запуск без изменений
- `--transfers=4` - количество одновременных передач (по умолчанию 4)
- `--checkers=8` - количество проверщиков (по умолчанию 8)

### Способ 2: AWS CLI

**Установка:**

```bash
# Windows (PowerShell)
# Скачайте с https://aws.amazon.com/cli/
# Или через Chocolatey:
choco install awscli

# Linux
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip awscliv2.zip
sudo ./aws/install
```

**Настройка профилей:**

```bash
# Yandex Cloud
aws configure --profile yandex
# Введите:
# AWS Access Key ID: ВАШ_YANDEX_KEY
# AWS Secret Access Key: ВАШ_YANDEX_SECRET
# Default region name: ru-central1
# Default output format: json

# Selectel
aws configure --profile selectel
# Введите:
# AWS Access Key ID: ВАШ_SELECTEL_KEY
# AWS Secret Access Key: ВАШ_SELECTEL_SECRET
# Default region name: ru-1
# Default output format: json

# Wasabi
aws configure --profile wasabi
# Введите:
# AWS Access Key ID: ВАШ_WASABI_KEY
# AWS Secret Access Key: ВАШ_WASABI_SECRET
# Default region name: eu-central-1
# Default output format: json
```

**Синхронизация данных:**

```bash
# Синхронизация Yandex → Selectel
aws s3 sync s3://ваш-бакет s3://ваш-бакет \
  --profile yandex \
  --endpoint-url https://storage.yandexcloud.net \
  --source-region ru-central1 \
  --region ru-1 \
  --endpoint-url https://s3.selcdn.ru

# Синхронизация Yandex → Wasabi
aws s3 sync s3://ваш-бакет s3://ваш-бакет \
  --profile yandex \
  --endpoint-url https://storage.yandexcloud.net \
  --source-region ru-central1 \
  --profile wasabi \
  --endpoint-url https://s3.wasabisys.com \
  --region eu-central-1
```

### Способ 3: Python скрипт

```python
#!/usr/bin/env python
"""
Скрипт для миграции данных между S3-провайдерами
"""

import os
import boto3
from botocore.session import Session

def sync_buckets(source_endpoint, source_key, source_secret, source_bucket,
                 dest_endpoint, dest_key, dest_secret, dest_bucket):
    """Синхронизирует файлы между двумя S3-бакетами"""
    
    # Создаём сессии для источника и назначения
    source_session = Session()
    source_client = source_session.client(
        's3',
        endpoint_url=source_endpoint,
        aws_access_key_id=source_key,
        aws_secret_access_key=source_secret,
        region_name='ru-central1'
    )
    
    dest_session = Session()
    dest_client = dest_session.client(
        's3',
        endpoint_url=dest_endpoint,
        aws_access_key_id=dest_key,
        aws_secret_access_key=dest_secret,
        region_name='ru-1'
    )
    
    # Получаем список всех объектов в исходном бакете
    print(f"Получение списка файлов из {source_bucket}...")
    source_objects = []
    paginator = source_client.get_paginator('list_objects_v2')
    
    for page in paginator.paginate(Bucket=source_bucket):
        if 'Contents' in page:
            source_objects.extend(page['Contents'])
    
    print(f"Найдено {len(source_objects)} файлов")
    
    # Копируем файлы
    for i, obj in enumerate(source_objects, 1):
        key = obj['Key']
        print(f"[{i}/{len(source_objects)}] Копирование: {key}")
        
        try:
            dest_client.copy_object(
                Bucket=dest_bucket,
                Key=key,
                CopySource={'Bucket': source_bucket, 'Key': key}
            )
        except Exception as e:
            print(f"❌ Ошибка при копировании {key}: {e}")
    
    print("✅ Синхронизация завершена!")

if __name__ == "__main__":
    # Настройки для Yandex → Selectel
    sync_buckets(
        source_endpoint='https://storage.yandexcloud.net',
        source_key='ВАШ_YANDEX_KEY',
        source_secret='ВАШ_YANDEX_SECRET',
        source_bucket='ваш-бакет',
        
        dest_endpoint='https://s3.selcdn.ru',
        dest_key='ВАШ_SELECTEL_KEY',
        dest_secret='ВАШ_SELECTEL_SECRET',
        dest_bucket='ваш-бакет'
    )
```

---

## ✅ Проверка после миграции

### 1. Проверка целостности данных

```bash
# Сравнение количества файлов
rclone ls yandex:ваш-бакет | wc -l
rclone ls selectel:ваш-бакет | wc -l

# Проверка контрольных сумм
rclone check yandex:ваш-бакет selectel:ваш-бакет
```

### 2. Проверка в Django

```bash
python manage.py shell
```

```python
from core.models import Event
from django.core.files.storage import default_storage

# Проверка всех мероприятий
events = Event.objects.all()
errors = []

for event in events:
    # Проверка изображения
    if event.image and not default_storage.exists(event.image.name):
        errors.append(f"Мероприятие {event.id}: файл {event.image.name} не найден")
    
    # Проверка видео
    if event.video_url and not default_storage.exists(event.video_url.name):
        errors.append(f"Мероприятие {event.id}: файл {event.video_url.name} не найден")
    
    # Проверка дополнительных изображений
    for image in event.images.all():
        if not default_storage.exists(image.image.name):
            errors.append(f"Изображение {image.id}: файл {image.image.name} не найден")

if errors:
    print("❌ Ошибки:")
    for error in errors[:10]:  # Показываем первые 10 ошибок
        print(error)
else:
    print("✅ Все файлы успешно найдены!")
```

### 3. Проверка доступа к файлам

```python
from core.models import Event

# Проверка URL-адресов
event = Event.objects.first()
if event:
    print(f"Image URL: {event.image.url}")
    print(f"Video URL: {event.video_url.url}")
    
    # Проверка доступности
    import requests
    response = requests.get(event.image.url)
    print(f"Статус изображения: {response.status_code}")
```

---

## 🔄 Переключение на новый провайдер

### Шаг 1: Остановите приложение

```bash
# Остановите сервер
# (или отключите веб-сервер)
```

### Шаг 2: Запустите финальную синхронизацию

```bash
# Синхронизация с учётом новых файлов
rclone sync yandex:ваш-бакет selectel:ваш-бакет \
  --checksum \
  --progress \
  --verbose
```

### Шаг 3: Измените `.env`

```env
# Было (Yandex Cloud)
USE_YANDEX_CLOUD=True

# Стало (Selectel)
USE_YANDEX_CLOUD=False
USE_SELECTEL_CLOUD=True
```

### Шаг 4: Перезапустите приложение

```bash
# Перезапустите веб-сервер
# (или запустите django runserver)
python manage.py runserver
```

### Шаг 5: Проверьте работу

```bash
# Откройте браузер и проверьте:
# - Просмотр мероприятий
# - Загрузка новых файлов
# - Удаление файлов
```

---

## 📊 Мониторинг после миграции

### Логирование

```bash
# Проверьте логи
tail -f debug.log
```

### Статистика

```bash
# Количество файлов в бакете
rclone lsf yandex:ваш-бакет | wc -l
rclone lsf selectel:ваш-бакет | wc -l

# Размер данных
rclone size yandex:ваш-бакет
rclone size selectel:ваш-бакет
```

---

## ⚠️ Важные замечания

### 1. **URL-адреса изменятся**

После переключения провайдера URL-адреса файлов будут другими:

**Yandex Cloud:**
```
https://storage.yandexcloud.net/ваш-бакет/event_images/image.jpg
```

**Selectel:**
```
https://s3.selcdn.ru/ваш-бакет/event_images/image.jpg
```

Django автоматически генерирует новые URL через `event.image.url`, так как в БД хранятся только пути.

### 2. **Кэширование**

Если используете CDN или браузерное кэширование:
- Очистите кэш CDN
- Настройте правильные заголовки Cache-Control

### 3. **Ссылки в email-рассылках**

Если в письмах отправлялись прямые ссылки на файлы - они перестанут работать. Рекомендуется использовать относительные ссылки.

### 4. **Откат**

Оставьте старый бакет включённым на 1-2 недели для отката в случае проблем:

```bash
# Временно верните старую конфигурацию
USE_YANDEX_CLOUD=True
USE_SELECTEL_CLOUD=False
```

---

## 🛠️ Устранение проблем

### Проблема: Файлы не видны после миграции

**Решение:**
1. Проверьте настройки прав доступа к бакету
2. Проверьте CORS-настройки
3. Убедитесь, что endpoint URL правильный

### Проблема: Медленная загрузка

**Решение:**
1. Включите CDN (если доступно)
2. Проверьте настройки региона
3. Оптимизируйте изображения/видео

### Проблема: Ошибки при загрузке

**Решение:**
1. Проверьте доступные квоты в новом провайдере
2. Проверьте лимиты на размер файлов
3. Проверьте настройки времени ожидания (timeout)

---

## 📚 Полезные ресурсы

- [rclone Documentation](https://rclone.org/)
- [rclone S3 Guide](https://rclone.org/s3/)
- [Selectel S3 Documentation](https://docs.selectel.ru/en/s3/about/about-s3/)
- [Wasabi Documentation](https://wasabi.com/docs/)
- [AWS CLI S3 Commands](https://docs.aws.amazon.com/cli/latest/reference/s3/)
- [Boto3 S3 Guide](https://boto3.amazonaws.com/v1/documentation/api/latest/guide/s3.html)

---

## 🎯 Резюме

1. **Подготовьте новый бакет** у выбранного провайдера
2. **Настройте переменные окружения** для нового провайдера
3. **Синхронизируйте данные** через rclone или AWS CLI
4. **Проверьте целостность** всех файлов
5. **Переключите приложение** на новый провайдер
6. **Мониторьте работу** в течение 1-2 недель
7. **Очистите старый бакет** после успешной миграции

Ваш проект уже готов к миграции! ✅
