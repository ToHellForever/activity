#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Скрипт для создания 5 тестовых площадок
"""
import os
import sys
import django
from datetime import datetime, timedelta
from decimal import Decimal

# Добавляем проект в путь
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'activity.settings')
django.setup()

from django.contrib.auth import get_user_model
from venues.models import Venue, VenueImage
from django.core.files.uploadedfile import SimpleUploadedFile
from io import BytesIO
from PIL import Image

User = get_user_model()

def create_test_image(filename, width=800, height=600, color=(200, 200, 200)):
    """Создаёт тестовое изображение"""
    img = Image.new('RGB', (width, height), color=color)
    buffer = BytesIO()
    img.save(buffer, format='JPEG')
    buffer.seek(0)
    return SimpleUploadedFile(filename, buffer.read(), content_type='image/jpeg')

def create_test_venues():
    print("=== Создание тестовых площадок ===\n")
    
    # 1. Создаём или получаем партнёра
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
        # Создаём профиль партнёра
        from partner_app.models import PartnerProfile
        PartnerProfile.objects.get_or_create(
            user=partner,
            defaults={
                'company_name': 'ООО "Конференц Сервис"',
                'phone': '+7 (999) 987-65-43',
                'contact_person': 'Петров Петр Петрович',
            }
        )
        print(f"[OK] Создан партнёр и профиль: {partner.partner_profile.company_name}")
    else:
        print(f"[OK] Партнёр уже существует: {partner.partner_profile.company_name}")
    
    # 2. Создаём типы площадок
    from venues.models import VenueType, VenueFormat
    
    venue_types = {
        'Конференц-зал': VenueType.objects.get_or_create(name='Конференц-зал')[0],
        'Переговорная': VenueType.objects.get_or_create(name='Переговорная')[0],
        'Тренинговый зал': VenueType.objects.get_or_create(name='Тренинговый зал')[0],
        'Большой зал': VenueType.objects.get_or_create(name='Большой зал')[0],
        'Коворкинг': VenueType.objects.get_or_create(name='Коворкинг')[0],
    }
    
    # Создаём форматы
    venue_formats = {
        'Семинар': VenueFormat.objects.get_or_create(name='Семинар')[0],
        'Тренинг': VenueFormat.objects.get_or_create(name='Тренинг')[0],
        'Конференция': VenueFormat.objects.get_or_create(name='Конференция')[0],
        'Мастер-класс': VenueFormat.objects.get_or_create(name='Мастер-класс')[0],
        'Бизнес-встреча': VenueFormat.objects.get_or_create(name='Бизнес-встреча')[0],
    }
    
    # 3. Создаём площадки
    venues_data = [
        {
            'title': 'Конференц зал',
            'description': 'Современный конференц-зал площадью 50 кв.м идеально подходит для деловых встреч, мастер-классов, семинаров и презентаций.',
            'address': 'г. Новосибирск, Мира, 119',
            'area': 50.0,
            'max_capacity': 30,
            'price': 15000.00,
            'venue_type': venue_types['Конференц-зал'],
            'formats': ['Семинар', 'Конференция'],
            'color': (255, 220, 180),
        },
        {
            'title': 'Переговорная',
            'description': 'Уютная переговорная комната для деловых встреч и переговоров до 20 человек.',
            'address': 'г. Новосибирск, Мира, 119',
            'area': 35.0,
            'max_capacity': 20,
            'price': 10000.00,
            'venue_type': venue_types['Переговорная'],
            'formats': ['Бизнес-встреча'],
            'color': (180, 230, 200),
        },
        {
            'title': 'Тренинговый зал',
            'description': 'Просторный тренинговый зал для обучающих программ и тренингов до 40 человек.',
            'address': 'г. Новосибирск, Мира, 119',
            'area': 75.0,
            'max_capacity': 40,
            'price': 20000.00,
            'venue_type': venue_types['Тренинговый зал'],
            'formats': ['Тренинг', 'Семинар'],
            'color': (200, 210, 255),
        },
        {
            'title': 'Большой зал',
            'description': 'Роскошный большой зал для масштабных мероприятий и конференций до 50 человек.',
            'address': 'г. Новосибирск, Мира, 119',
            'area': 100.0,
            'max_capacity': 50,
            'price': 25000.00,
            'venue_type': venue_types['Большой зал'],
            'formats': ['Конференция', 'Семинар'],
            'color': (255, 200, 220),
        },
        {
            'title': 'Коворкинг-пространство',
            'description': 'Гибкое коворкинг-пространство для работы и небольших встреч до 25 человек.',
            'address': 'г. Новосибирск, Мира, 119',
            'area': 80.0,
            'max_capacity': 25,
            'price': 18000.00,
            'venue_type': venue_types['Коворкинг'],
            'formats': ['Бизнес-встреча', 'Мастер-класс'],
            'color': (230, 255, 200),
        },
    ]
    
    # 4. Создаём площадки
    venues_created = []
    for i, data in enumerate(venues_data, 1):
        print(f"\n--- Создаём площадку {i}/5: {data['title']} ---")
        
        # Создаём площадку без slug (он генерируется в save())
        from django.utils.text import slugify
        from unidecode import unidecode
        
        venue = Venue(
            title=data['title'],
            description=data['description'],
            address=data['address'],
            area=data['area'],
            max_capacity=data['max_capacity'],
            price=data['price'],
            price_unit='event',
            venue_type=data['venue_type'],
            latitude=55.0084,
            longitude=82.9357,
            tariff=2,
            status='published',
            contact_info='+7 (999) 123-45-67\nEmail: venue@example.com',
            contacts_opened=True,
            meta_title=f"{data['title']} - Новосибирск",
            meta_description=data['description']
        )
        venue.save()  # Это сгенерирует slug
        
        # Добавляем форматы
        for fmt_name in data['formats']:
            if fmt_name in venue_formats:
                venue.formats.add(venue_formats[fmt_name])
        
        # Создаём изображение
        img = create_test_image(
            f'test_venue_{i}.jpg',
            color=data['color']
        )
        venue.images.create(image=img)
        
        # Создаём дополнительные фото (2 штуки)
        for j in range(2):
            extra_img = create_test_image(
                f'test_venue_{i}_extra_{j}.jpg',
                color=(data['color'][0] + 15, data['color'][1] + 15, data['color'][2] + 15)
            )
            venue.images.create(image=extra_img)
        
        venues_created.append(venue)
        print(f"[OK] Создана площадка ID: {venue.id}")
    
    print(f"\n=== Готово! Создано {len(venues_created)} площадок ===")
    print("\nДоступные площадки:")
    for venue in venues_created:
        print(f"  - {venue.title} ({venue.area} м², до {venue.max_capacity} чел.)")
        print(f"    URL: http://127.0.0.1:8000/venues/{venue.id}/")
    
    return venues_created

if __name__ == '__main__':
    create_test_venues()
