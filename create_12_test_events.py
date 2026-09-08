#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Скрипт для создания 12 тестовых активных мероприятий
(для проверки пагинации "Показать ещё": 9 на первой странице + 3 на второй).
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
from core.models import Event, Category, Format, Tag, EventPackage, UserPackageSubscription, EventImage
from django.core.files.uploadedfile import SimpleUploadedFile
from io import BytesIO
from PIL import Image

# Устанавливаем кодировку для Windows
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

User = get_user_model()

def create_test_image(filename, width=800, height=600, color=(200, 200, 200)):
    """Создаёт тестовое изображение"""
    img = Image.new('RGB', (width, height), color=color)
    buffer = BytesIO()
    img.save(buffer, format='JPEG')
    buffer.seek(0)
    return SimpleUploadedFile(filename, buffer.read(), content_type='image/jpeg')


def create_test_events():
    print("=== Создание 12 тестовых мероприятий ===\n")

    # 1. Партнёр
    partner, created = User.objects.get_or_create(
        username='test_partner_12',
        defaults={
            'email': 'test_12events@example.com',
            'first_name': 'Тестовый',
            'last_name': 'Организатор',
            'user_type': 'partner',
            'is_verified': True,
            'verification_status': 'approved',
        }
    )
    if created:
        partner.set_password('password123')
        partner.save()
        from partner_app.models import PartnerProfile
        PartnerProfile.objects.get_or_create(
            user=partner,
            defaults={
                'company_name': 'ООО "Двенадцать Месяцев"',
                'phone': '+7 (999) 555-12-12',
                'contact_person': 'Петров Пётр Петрович',
            }
        )
        print(f"[OK] Создан партнёр: {partner.partner_profile.company_name}")
    else:
        print(f"[OK] Партнёр уже существует: {partner.partner_profile.company_name}")

    # 2. Пакет "Приоритет" (уже существует в БД, лимит 5 -> расширяем до 50)
    package, created = EventPackage.objects.get_or_create(
        name='Приоритет',
        defaults={
            'price': 50000.00,
            'max_active_events': 50,
            'event_card_type': 'priority',
            'description_type': 'detailed',
            'has_program_and_speakers': True,
            'max_photos': 10,
            'has_video': True,
            'has_platform_request': True,
            'has_free_registration': True,
            'has_ticket_sales': True,
            'visibility_level': 'priority',
            'has_collection_participation': True,
            'is_monthly': True,
        }
    )
    if package.max_active_events < 12:
        package.max_active_events = 50
        package.save()
    print(f"[OK] Пакет: {package.name} (лимит {package.max_active_events} мероприятий)")

    # 3. Подписка
    subscription, created = UserPackageSubscription.objects.get_or_create(
        user=partner,
        package=package,
        defaults={'is_active': True, 'subscription_type': 'monthly'}
    )
    if not created:
        subscription.is_active = True
        subscription.save()
    print(f"[OK] Подписка активна")

    # 4. Категории
    categories = {}
    for name in ['Маркетинг', 'Продажи', 'Управление', 'Финансы', 'IT и Технологии', 'HR']:
        cat, _ = Category.objects.get_or_create(name=name)
        categories[name] = cat

    # 5. Форматы
    formats = {}
    for name in ['Конференция', 'Семинар', 'Тренинг', 'Форум', 'Мастер-класс', 'Вебинар']:
        fmt, _ = Format.objects.get_or_create(name=name)
        formats[name] = fmt

    # 6. Данные 12 мероприятий
    events_data = [
        ('Мастер-класс: SMM для бизнеса с нуля', 'Маркетинг', 'Мастер-класс', 3, 1500, (255, 200, 150)),
        ('Конференция "Digital-маркетинг 2026"', 'Маркетинг', 'Конференция', 5, 3000, (255, 180, 130)),
        ('Тренинг: холодные продажи без страха', 'Продажи', 'Тренинг', 7, 2500, (255, 220, 200)),
        ('Семинар: B2B-переговоры высшего уровня', 'Продажи', 'Семинар', 9, 2800, (250, 200, 220)),
        ('Форум предпринимателей Сибири', 'Управление', 'Форум', 11, 5000, (180, 220, 255)),
        ('Тренинг по лидерству для руководителей', 'Управление', 'Тренинг', 13, 3500, (200, 210, 255)),
        ('Финансовая грамотность для бизнеса', 'Финансы', 'Семинар', 15, 4000, (200, 250, 200)),
        ('Налоговое планирование: практикум', 'Финансы', 'Мастер-класс', 17, 3200, (170, 240, 190)),
        ('Внедрение ИИ в бизнес-процессы', 'IT и Технологии', 'Конференция', 19, 6000, (220, 200, 255)),
        ('Автоматизация продаж через CRM', 'IT и Технологии', 'Вебинар', 21, 1800, (230, 210, 250)),
        ('HR-аналитика: подбор команды мечты', 'HR', 'Семинар', 23, 2700, (255, 250, 200)),
        ('Онбординг сотрудников: лучшие практики', 'HR', 'Тренинг', 25, 2200, (250, 245, 180)),
    ]

    # 7. Создание мероприятий
    created_events = []
    for i, (title, cat_name, fmt_name, offset_days, price, color) in enumerate(events_data, 1):
        # Пропускаем, если мероприятие с таким названием уже есть
        if Event.objects.filter(title=title, organizer=partner).exists():
            print(f"[SKIP] Мероприятие {i}/12 уже существует: {title[:50]}")
            continue

        event_date = datetime.now() + timedelta(days=offset_days)
        event = Event.objects.create(
            organizer=partner,
            title=title,
            description=f'Тестовое мероприятие №{i}. {title} — практическое занятие с экспертами отрасли. '
                        f'Программа включает лекционную часть, разбор кейсов и нетворкинг.',
            date_time=event_date,
            category=categories[cat_name],
            format=formats[fmt_name],
            status='active',
            place_data={
                'address': 'г. Новосибирск, Мира, 119',
                'latitude': 55.0084,
                'longitude': 82.9357,
            },
            duration='03:00',
            commission_rate=Decimal('10.00'),
            package=package,
        )

        # Изображение
        img = create_test_image(f'test12_event_{i}.jpg', color=color)
        event.image.save(f'test12_event_{i}.jpg', img, save=True)

        # Дополнительное фото
        extra_img = create_test_image(
            f'test12_event_{i}_extra.jpg',
            color=(min(color[0] + 30, 255), min(color[1] + 30, 255), min(color[2] + 30, 255))
        )
        EventImage.objects.create(event=event, image=extra_img)

        # Билеты
        for ticket_name, ticket_price in [
            ('Раннее бронирование', price),
            ('Стандарт', int(price * 1.5)),
            ('VIP', int(price * 2.5)),
        ]:
            event.tickets.create(name=ticket_name, price=ticket_price, available_quantity=50)

        created_events.append(event)
        print(f"[OK] Мероприятие {i}/12 создано: {title[:60]}")

    print(f"\n=== Готово! Создано новых мероприятий: {len(created_events)} ===")
    total = Event.objects.filter(organizer=partner, status='active').count()
    print(f"Всего активных мероприятий тестового партнёра: {total}")
    print("Проверка пагинации: http://127.0.0.1:8000/events/ (9 карточек + кнопка 'Показать ещё')")


if __name__ == '__main__':
    create_test_events()
