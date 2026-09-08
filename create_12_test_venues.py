#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Скрипт для создания 12 тестовых площадок
(для проверки пагинации "Показать ещё": 12 на первой странице + следующие порции).
"""
import os
import sys
import django

# Добавляем проект в путь
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'activity.settings')
django.setup()

from django.contrib.auth import get_user_model
from venues.models import Venue, VenueType, VenueFormat
from django.core.files.uploadedfile import SimpleUploadedFile
from io import BytesIO
from PIL import Image

User = get_user_model()

# Устанавливаем кодировку для Windows
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')


def create_test_image(filename, width=800, height=600, color=(200, 200, 200)):
    """Создаёт тестовое изображение"""
    img = Image.new('RGB', (width, height), color=color)
    buffer = BytesIO()
    img.save(buffer, format='JPEG')
    buffer.seek(0)
    return SimpleUploadedFile(filename, buffer.read(), content_type='image/jpeg')


def create_test_venues():
    print("=== Создание 12 тестовых площадок ===\n")

    # 1. Партнёр
    partner, created = User.objects.get_or_create(
        username='test_partner_venue',
        defaults={
            'email': 'test_venue@example.com',
            'first_name': 'Площадки',
            'last_name': 'Партнёр',
            'user_type': 'partner',
            'is_verified': True,
            'verification_status': 'approved',
        }
    )
    if created:
        partner.set_password('password123')
        partner.save()

    from partner_app.models import PartnerProfile
    profile, profile_created = PartnerProfile.objects.get_or_create(
        user=partner,
        defaults={
            'company_name': 'ООО "Конференц Сервис"',
            'phone': '+7 (999) 987-65-43',
            'contact_person': 'Петров Пётр Петрович',
        }
    )
    if profile_created:
        print(f"[OK] Создан профиль партнёра: {profile.company_name}")
    else:
        print(f"[OK] Партнёр и профиль уже существуют: {profile.company_name}")

    # 2. Типы площадок
    venue_types = {}
    for name in ['Конференц-зал', 'Переговорная', 'Тренинговый зал', 'Большой зал', 'Коворкинг', 'Лекторий']:
        venue_types[name] = VenueType.objects.get_or_create(name=name)[0]

    # 3. Форматы
    venue_formats = {}
    for name in ['Семинар', 'Тренинг', 'Конференция', 'Мастер-класс', 'Бизнес-встреча']:
        venue_formats[name] = VenueFormat.objects.get_or_create(name=name)[0]

    # 4. Данные 12 площадок
    # (название, тип, площадь, вместимость, цена, форматы, цвет, адрес, этаж-деталь в описании)
    venues_data = [
        ('Конференц-зал «Мира»', 'Конференц-зал', 50, 30, 15000, ['Семинар', 'Конференция'], (255, 220, 180), 'г. Новосибирск, ул. Мира, 119'),
        ('Переговорная «Компас»', 'Переговорная', 35, 20, 10000, ['Бизнес-встреча'], (180, 230, 200), 'г. Новосибирск, ул. Мира, 119'),
        ('Тренинговый зал «Старт»', 'Тренинговый зал', 75, 40, 20000, ['Тренинг', 'Семинар'], (200, 210, 255), 'г. Новосибирск, ул. Ленина, 12'),
        ('Большой зал «Панорама»', 'Большой зал', 100, 50, 25000, ['Конференция', 'Семинар'], (255, 200, 220), 'г. Новосибирск, ул. Ленина, 12'),
        ('Коворкинг «Точка роста»', 'Коворкинг', 80, 25, 18000, ['Бизнес-встреча', 'Мастер-класс'], (230, 255, 200), 'г. Новосибирск, Красный проспект, 25'),
        ('Лекторий «Знание»', 'Лекторий', 60, 45, 16000, ['Семинар', 'Мастер-класс'], (255, 240, 180), 'г. Новосибирск, Красный проспект, 25'),
        ('Конференц-зал «Сибирь»', 'Конференц-зал', 90, 60, 28000, ['Конференция'], (200, 230, 255), 'г. Новосибирск, ул. Советская, 64'),
        ('Переговорная «Диалог»', 'Переговорная', 30, 15, 8000, ['Бизнес-встреча'], (220, 255, 220), 'г. Новосибирск, ул. Советская, 64'),
        ('Тренинговый зал «Прогресс»', 'Тренинговый зал', 70, 35, 19000, ['Тренинг'], (255, 210, 210), 'г. Новосибирск, ул. Кирова, 113'),
        ('Большой зал «Вертикаль»', 'Большой зал', 120, 80, 35000, ['Конференция', 'Семинар'], (210, 200, 255), 'г. Новосибирск, ул. Кирова, 113'),
        ('Коворкинг «Лофт»', 'Коворкинг', 95, 30, 21000, ['Бизнес-встреча', 'Мастер-класс'], (255, 230, 200), 'г. Новосибирск, ул. Депутатская, 46'),
        ('Лекторий «Амфитеатр»', 'Лекторий', 85, 70, 24000, ['Семинар', 'Конференция'], (200, 255, 240), 'г. Новосибирск, ул. Депутатская, 46'),
    ]

    # 5. Создание площадок
    created_venues = []
    for i, (title, type_name, area, capacity, price, formats, color, address) in enumerate(venues_data, 1):
        # Пропускаем дубликаты (площадка с таким названием у этого партнёра)
        if Venue.objects.filter(title=title).exists():
            print(f"[SKIP] Площадка {i}/12 уже существует: {title}")
            continue

        venue = Venue(
            title=title,
            description=f'Тестовая площадка №{i}. «{title}» — {area} м² для {capacity} человек. '
                        f'Современное оснащение: проектор, экран, флипчарт, кондиционер, Wi-Fi. '
                        f'Идеально подходит для деловых мероприятий любого формата.',
            address=address,
            area=float(area),
            max_capacity=capacity,
            price=price,
            price_unit='event',
            venue_type=venue_types[type_name],
            latitude=55.0084,
            longitude=82.9357,
            tariff=(i % 3) + 1,  # Разные тарифы 1-3 для проверки бейджей и сортировки
            status='published',
            contact_info='+7 (999) 123-45-67\nEmail: venue@example.com',
            contacts_opened=True,
            meta_title=f"{title} - Новосибирск",
            meta_description=f'Аренда {type_name.lower()} в Новосибирске: {area} м², до {capacity} человек.',
        )
        venue.save()  # slug генерируется в save()

        # Форматы
        for fmt_name in formats:
            venue.formats.add(venue_formats[fmt_name])

        # Основное изображение
        img = create_test_image(f'test12_venue_{i}.jpg', color=color)
        venue.images.create(image=img)

        # Дополнительные фото (2 шт.)
        for j in range(2):
            extra_img = create_test_image(
                f'test12_venue_{i}_extra_{j}.jpg',
                color=(min(color[0] + 20, 255), min(color[1] + 20, 255), min(color[2] + 20, 255))
            )
            venue.images.create(image=extra_img)

        created_venues.append(venue)
        print(f"[OK] Площадка {i}/12 создана: {title}")

    print(f"\n=== Готово! Создано новых площадок: {len(created_venues)} ===")
    total = Venue.objects.filter(status='published').count()
    print(f"Всего опубликованных площадок в БД: {total}")
    print("Проверка пагинации: http://127.0.0.1:8000/venues/ (12 карточек + кнопка 'Показать ещё')")


if __name__ == '__main__':
    create_test_venues()
