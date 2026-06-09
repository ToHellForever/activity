# Настройка обработки медиафайлов с загрузкой в Yandex Cloud

## Что было реализовано

Система теперь обрабатывает изображения и видео **на сервере перед загрузкой** в Yandex Object Storage:

### Для изображений:
1. ✅ Конвертация в JPEG (для PNG, GIF, WEBP)
2. ✅ Изменение размера до 800x600 пикселей
3. ✅ Сжатие с качеством 85%
4. ✅ Добавление водяного знака
5. ✅ Удаление временных файлов после загрузки

### Для видео:
1. ✅ Сжатие видео (H.264, 2500k битрейт)
2. ✅ Сжатие аудио (AAC, 128k)
3. ✅ Добавление водяного знака
4. ✅ Оптимизация для веб-стриминга
5. ✅ Удаление временных файлов после загрузки

## Созданные файлы

```
core/
├── storage_backends.py    # Базовое хранилище с обработкой
├── image_storage.py       # Хранилище для изображений  
├── video_storage.py       # Хранилище для видео
├── storage.py             # Утилиты для получения хранилищ
├── apps.py                # Инициализация хранилищ (обновлён)
├── models.py              # Модели (обновлены поля image/video_url)
└── storage_docs.md        # Подробная документация

activity/
└── settings.py            # Настройки (обновлены)

.
├── .env.yandex.example    # Пример переменных окружения
└── STORAGE_SETUP.md       # Эта инструкция
```

## Как включить

### Шаг 1: Установите зависимости

```powershell
pip install django-storages boto3 pillow moviepy opencv-python
```

### Шаг 2: Настройте переменные окружения

Скопируйте `.env.yandex.example` в `.env` и заполните:

```env
USE_YANDEX_CLOUD=True
YANDEX_CLOUD_ACCESS_KEY_ID=ваш_access_key
YANDEX_CLOUD_SECRET_ACCESS_KEY=ваш_secret_key
YANDEX_CLOUD_BUCKET_name=ваш_бакет
YANDEX_CLOUD_ENDPOINT_URL=https://storage.yandexcloud.net
```

### Шаг 3: Создайте водяной знак

Положите файл `watermark.png` в папку `media/`:

```
media/
└── watermark.png
```

### Шаг 4: Проверьте настройку

```powershell
python manage.py check
```

## Как это работает

### При создании/редактировании мероприятия:

1. **Пользователь загружает фото/видео**
   - Файл приходит через форму в `partner_app/views.py`

2. **Сохранение в модели**
   - `Event.save()` или `EventImage.save()` вызывается
   - Файл сохраняется во временную директорию `media_temp/`

3. **Обработка**
   - `YandexImageProcessingStorage._process_file()` или
   - `YandexVideoProcessingStorage._process_file()`
   - Применяются: сжатие, изменение размера, водяной знак

4. **Загрузка в Yandex Cloud**
   - Обработанный файл загружается в бакет
   - Временные файлы удаляются

5. **Отображение на сайте**
   - `{{ event.image.url }}` возвращает URL из Yandex Cloud

## Режимы работы

### Локальная разработка (по умолчанию)

```env
USE_YANDEX_CLOUD=False
```

- Файлы сохраняются в `media/`
- Обработка не применяется
- Быстро для разработки

### Продакшен с Yandex Cloud

```env
USE_YANDEX_CLOUD=True
```

- Файлы обрабатываются на сервере
- Загружаются в Yandex Object Storage
- Временные файлы удаляются

## Модели, использующие кастомные хранилища

| Модель | Поле | Тип | Обработка |
|--------|------|-----|-----------|
| `Event` | `image` | Изображение | ✅ Да |
| `Event` | `video_url` | Видео | ✅ Да |
| `EventImage` | `image` | Изображение | ✅ Да |

## Отключение обработки

Если нужно использовать стандартное хранилище Yandex Cloud без обработки:

**Вариант 1:** В `core/apps.py` закомментируйте:
```python
def ready(self):
    import core.signals
    import core.proxy_models
    # self.apply_storage_backends()  # Закомментировать
```

**Вариант 2:** Удалите из `apps.py` метод `apply_storage_backends()`

## Мониторинг

### Логи

Все ошибки логируются. Проверьте `debug.log`:

```powershell
Get-Content debug.log -Tail 50
```

### Временные файлы

Очистка `media_temp/` при необходимости:

```powershell
Remove-Item -Recurse -Force media_temp\*
```

## Тестирование

### 1. Создайте тестовое мероприятие

- Зайдите как партнёр
- Создайте новое мероприятие
- Загрузите изображение и видео

### 2. Проверьте результат

```powershell
python manage.py shell
```

```python
from core.models import Event, EventImage

# Проверка изображения
event = Event.objects.first()
print(f"Image URL: {event.image.url}")
print(f"Storage type: {type(event.image.storage)}")

# Проверка хранилища
if event.image:
    print(f"File exists: {event.image.storage.exists(event.image.name)}")
```

## Получение доступа к Yandex Cloud

### Способ 1: Service Account

1. Создайте сервисный аккаунт в Yandex Cloud
2. Дайте роль `storage.editor`
3. Создайте Access Key
4. Используйте в `.env`

### Способ 2: IAM Token

1. Аутентифицируйтесь через `yc` CLI
2. Получите IAM token
3. Настройте аутентификацию в коде

## Производительность

### Ожидаемое время обработки:

| Тип | Размер | Время |
|-----|--------|-------|
| Изображение | 5MB | 1-2 сек |
| Видео | 50MB | 10-30 сек |
| Видео | 200MB | 1-2 мин |

### Улучшение производительности:

1. **Celery** - для асинхронной обработки
2. **CDN** - для ускорения доставки
3. **Кэширование** - для частых запросов

## Устранение проблем

### Проблема: "No module named 'storages'"

```powershell
pip install django-storages
```

### Проблема: "Файл водяного знака не найден"

Проверьте наличие `media/watermark.png`

### Проблема: "Не удалось сжать видео"

Установите ffmpeg:

```powershell
# Windows
choco install ffmpeg

# Linux
apt-get install ffmpeg
```

### Проблема: Временные файлы не удаляются

Проверьте права доступа к `media_temp/`:

```powershell
icacls media_temp /grant Users:F
```

## Дополнительная информация

- Подробная документация: `core/storage_docs.md`
- Примеры переменных: `.env.yandex.example`
- Исходный код: `core/storage_backends.py`, `core/image_storage.py`, `core/video_storage.py`

## Следующие шаги

1. ✅ Настроить Yandex Cloud бакет
2. ✅ Получить Access/Secret keys
3. ✅ Установить зависимости
4. ✅ Настроить `.env`
5. ✅ Добавить водяной знак
6. ✅ Протестировать загрузку
7. ✅ Настроить CDN (опционально)

Готово! Теперь ваши медиафайлы обрабатываются на сервере перед загрузкой в Yandex Cloud.
