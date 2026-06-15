#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Скрипт для создания 5 тестовых мероприятий с пакетом "Приоритет"
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
from core.models import Event, Category, Format, Tag, EventPackage, UserPackageSubscription
from django.core.files.uploadedfile import SimpleUploadedFile
import requests
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
    print("=== Создание тестовых мероприятий ===\n")
    
    # 1. Создаём или получаем партнёра
    partner, created = User.objects.get_or_create(
        username='test_partner_prioritet',
        defaults={
            'email': 'test_prioritet@example.com',
            'first_name': 'Тестовый',
            'last_name': 'Партнёр',
            'user_type': 'partner',
            'is_verified': True,
            'verification_status': 'approved',
            'company_name': 'ООО "Бизнес Решения"',
            'phone_number': '+7 (999) 123-45-67',
            'contact_person': 'Иванов Иван Иванович'
        }
    )
    if created:
        partner.set_password('password123')
        partner.save()
        print(f"[OK] Создан партнёр: {partner.company_name}")
    else:
        print(f"[OK] Партнёр уже существует: {partner.company_name}")
    
    # 2. Получаем или создаём пакет "Приоритет"
    package, created = EventPackage.objects.get_or_create(
        name='Приоритет',
        defaults={
            'price': 50000.00,
            'max_active_events': 5,
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
            'is_monthly': True
        }
    )
    if created:
        print(f"✓ Создан пакет: {package.name}")
    else:
        print(f"✓ Пакет уже существует: {package.name}")
    
    # 3. Создаём или обновляем подписку партнёра
    subscription, created = UserPackageSubscription.objects.get_or_create(
        user=partner,
        package=package,
        defaults={
            'is_active': True,
            'subscription_type': 'monthly'
        }
    )
    if created:
        print(f"✓ Создана подписка на пакет {package.name}")
    else:
        subscription.is_active = True
        subscription.save()
        print(f"✓ Подписка активирована")
    
    # 4. Создаём категории если их нет
    categories_data = [
        ('Маркетинг', 'Категория для маркетинговых мероприятий'),
        ('Продажи', 'Категория для мероприятий по продажам'),
        ('Управление', 'Категория для управленческих мероприятий'),
        ('Финансы', 'Категория для финансовых мероприятий'),
        ('IT и Технологии', 'Категория для IT мероприятий'),
    ]
    
    categories = {}
    for name, desc in categories_data:
        cat, _ = Category.objects.get_or_create(name=name)
        categories[name] = cat
    
    # 5. Создаём форматы
    formats_data = ['Конференция', 'Семинар', 'Тренинг', 'Форум', 'Мастер-класс']
    formats = {}
    for name in formats_data:
        fmt, _ = Format.objects.get_or_create(name=name)
        formats[name] = fmt
    
    # 6. Создаём теги
    tags_data = [
        ('Digital-маркетинг', 'Маркетинг'),
        ('SMM', 'Маркетинг'),
        ('Таргетированная реклама', 'Маркетинг'),
        ('B2B продажи', 'Продажи'),
        ('Холодные звонки', 'Продажи'),
        ('Переговоры', 'Продажи'),
        ('Лидерство', 'Управление'),
        ('Менеджмент', 'Управление'),
        ('Стратегическое планирование', 'Управление'),
        ('Финансовый анализ', 'Финансы'),
        ('Бухгалтерский учёт', 'Финансы'),
        ('Налоговое планирование', 'Финансы'),
        ('Цифровая трансформация', 'IT и Технологии'),
        ('Искусственный интеллект', 'IT и Технологии'),
        ('Автоматизация бизнеса', 'IT и Технологии'),
    ]
    
    tags = {}
    for name, main_tag_name in tags_data:
        main_tag, _ = Tag._meta.get_field('main_tag').related_model.objects.get_or_create(name=main_tag_name)
        tag, _ = Tag.objects.get_or_create(name=name, defaults={'main_tag': main_tag})
        tags[name] = tag
    
    # 7. Создаём 5 мероприятий
    events_data = [
        {
            'title': 'Обучающая программа "Продвижение и реклама в социальных сетях"',
            'description_short': 'Интенсивная обучающая программа, посвящённая современным инструментам и стратегиям продвижения бизнеса в социальных сетях.',
            'description_full': '''Приглашаем вас принять участие в интенсивной обучающей программе, посвящённой современным инструментам и стратегиям продвижения бизнеса в социальных сетях!

Для кого эта программа:
• Собственников бизнеса, руководителей по маркетингу
• SMM-специалистов и начинающих маркетологов
• Всех, кто хочет эффективно использовать соцсети для продвижения своих проектов

Что вас ждёт:
• Полный разбор самых актуальных платформ: ВКонтакте, Instagram*, Telegram, Одноклассники, TikTok
• Эффективные инструменты создания и ведения продающих страниц
• Пошаговая настройка таргетированной и контекстной рекламы
• Продвинутые способы работы с аудиторией, увеличения вовлечённости и привлечения новых клиентов
• Обзор трендов SMM и анализа кейсов успешных брендов
• Практические задания и работа над собственными проектами прямо на конференции
• Разбор типичных ошибок и успешных стратегий
• Возможность задать вопросы опытным экспертам и получать ценные рекомендации''',
            'category': 'Маркетинг',
            'format': 'Конференция',
            'tags': ['Digital-маркетинг', 'SMM', 'Таргетированная реклама'],
            'date_offset_days': 10,
            'price_base': 2000,
            'color': (255, 200, 150),
        },
        {
            'title': 'Предпринимательская деятельность: от идеи до реализации',
            'description_short': 'Полный курс по запуску собственного бизнеса: от генерации идеи до первых продаж и масштабирования.',
            'description_full': '''Добро пожаловать на интенсивный курс для начинающих предпринимателей!

Для кого эта программа:
• Для тех, у кого есть идея, но нет плана реализации
• Для начинающих предпринимателей, которые хотят избежать типичных ошибок
• Для действующих бизнесов, планирующих масштабирование

Что вы получите:
• Методики генерации и проверки бизнес-идей
• Бизнес-моделирование и финансовое планирование
• Юридические аспекты открытия бизнеса
• Поиск инвестиций и работа с инвесторами
• Построение команды и управление персоналом
• Маркетинг и продажи для стартапов
• Кейсы успешных российских предпринимателей
• Практические задания по разработке вашего бизнес-плана

По итогам курса вы представите свой бизнес-проект перед экспертами и получите обратную связь!''',
            'category': 'Управление',
            'format': 'Семинар',
            'tags': ['Лидерство', 'Менеджмент', 'Стратегическое планирование'],
            'date_offset_days': 15,
            'price_base': 3500,
            'color': (180, 220, 255),
        },
        {
            'title': 'Холодные звонки: перспектива продаж в 2026 году',
            'description_short': 'Современные техники холодных звонков, работа с возражениями и построение воронки продаж.',
            'description_full': '''Холодные звонки не умирают — они эволюционируют!

На этом практическом семинаре вы освоите:

Современные подходы к холодным звонкам:
• Подготовка к звонку: исследование клиента и постановка целей
• Первые 30 секунд: как захватить внимание собеседника
• Техники установления раппорта и доверия
• Работа с секретарями и ЛПР

Работа с возражениями:
• "Мне не интересно" — как переубедить
• "Пришлите на почту" — как не потерять контакт
• "Дорого" — работа с ценовыми возражениями
• "Я подумаю" — как закрыть сделку здесь и сейчас

Построение воронки продаж:
• Метрики холодных звонков: что отслеживать
• Оптимизация скриптов на основе данных
• Интеграция холодных звонков с другими каналами
• CRM-системы для управления звонками

Практика:
• Запись и разбор ваших звонков
• Ролевые игры с тренерами
• Разбор реальных кейсов из B2B сектора''',
            'category': 'Продажи',
            'format': 'Семинар',
            'tags': ['B2B продажи', 'Холодные звонки', 'Переговоры'],
            'date_offset_days': 7,
            'price_base': 2500,
            'color': (255, 220, 200),
        },
        {
            'title': 'Финансовая грамотность для предпринимателей',
            'description_short': 'Управление финансами бизнеса: от бухгалтерского учёта до финансового планирования и оптимизации налогов.',
            'description_full': '''Ключевые финансовые навыки для успешного предпринимателя!

Программа курса:

Базовый финансовый учёт:
• Виды бухгалтерского учёта для малого бизнеса
• Основные финансовые отчёты: что и как читать
• Управленческая отчётность: cash flow, P&L, баланс
• Автоматизация учёта: современные инструменты

Финансовое планирование:
• Бюджетирование бизнеса
• Прогнозирование денежных потоков
• Точка безубыточности и план продаж
• Финансовые риски и как их минимизировать

Налоговое планирование:
• Выбор оптимальной налоговой системы
• Легальные способы оптимизации налогов
• Налоговые льготы для малого бизнеса
• Работа с налоговой инспекцией

Кейсы и практика:
• Разбор реальных финансовых ситуаций
• Расчет финансовых показателей вашего бизнеса
• Чек-листы и шаблоны документов
• Индивидуальные консультации''',
            'category': 'Финансы',
            'format': 'Тренинг',
            'tags': ['Финансовый анализ', 'Бухгалтерский учёт', 'Налоговое планирование'],
            'date_offset_days': 20,
            'price_base': 4000,
            'color': (200, 250, 200),
        },
        {
            'title': 'Цифровая трансформация бизнеса: стратегии и инструменты',
            'description_short': 'Как внедрить цифровые технологии в бизнес-процессы и повысить эффективность компании.',
            'description_full': '''Станьте лидером цифровой трансформации!

Актуальность темы:
В эпоху цифровизации компании, которые не внедряют современные технологии, теряют конкурентные преимущества. Этот форум поможет вам разобраться в стратегиях и инструментах цифровой трансформации.

Что вы изучите:

Стратегия цифровой трансформации:
• Оценка текущего уровня цифровизации бизнеса
• Построение дорожной карты трансформации
• Приоритизация проектов и распределение ресурсов
• Измерение ROI цифровых инициатив

Ключевые технологии:
• Облачные решения для бизнеса
• Искусственный интеллект и машинное обучение
• Автоматизация процессов (RPA)
• Аналитика больших данных
• IoT в производстве и логистике

Управление изменениями:
• Как подготовить команду к цифровым изменениям
• Преодоление сопротивления сотрудников
• Обучение и развитие цифровых компетенций
• Культура данных и экспериментов

Практические сессии:
• Работа в группах над реальными кейсами
• Демонстрация успешных внедрений
• Нетворкинг с CIO и CTO ведущих компаний
• Консультации экспертов по вашим проектам''',
            'category': 'IT и Технологии',
            'format': 'Форум',
            'tags': ['Цифровая трансформация', 'Искусственный интеллект', 'Автоматизация бизнеса'],
            'date_offset_days': 25,
            'price_base': 5000,
            'color': (220, 200, 255),
        },
    ]
    
    # 8. Создаём мероприятия
    events_created = []
    for i, data in enumerate(events_data, 1):
        print(f"\n--- Создаём мероприятие {i}/5: {data['title'][:50]}... ---")
        
        # Создаём событие
        event_date = datetime.now() + timedelta(days=data['date_offset_days'])
        event = Event.objects.create(
            organizer=partner,
            title=data['title'],
            description_short=data['description_short'],
            description_full=data['description_full'],
            date_time=event_date,
            category=categories[data['category']],
            format=formats[data['format']],
            status='active',
            place_data={
                'address': 'г. Новосибирск, Мира, 119',
                'latitude': 55.0084,
                'longitude': 82.9357,
            },
            duration='03:00',
            commission_rate=Decimal('10.00'),
            package=package
        )
        
        # Добавляем теги
        for tag_name in data['tags']:
            if tag_name in tags:
                event.tags.add(tags[tag_name])
        
        # Создаём изображение
        img = create_test_image(
            f'test_event_{i}.jpg',
            color=data['color']
        )
        event.image.save(f'test_event_{i}.jpg', img, save=True)  # save=True чтобы сохранить сразу
        
        # Создаём дополнительные фото (3 штуки)
        from core.models import EventImage
        for j in range(3):
            extra_img = create_test_image(
                f'test_event_{i}_extra_{j}.jpg',
                color=(data['color'][0] + 20, data['color'][1] + 20, data['color'][2] + 20)
            )
            EventImage.objects.create(
                event=event,
                image=extra_img
            )
        
        # Создаём билеты
        ticket_types = [
            ('Раннее бронирование', data['price_base']),
            ('Стандарт', int(data['price_base'] * 1.5)),
            ('VIP', int(data['price_base'] * 2.5)),
        ]
        
        for ticket_name, price in ticket_types:
            event.tickets.create(
                name=ticket_name,
                price=price,
                available_quantity=50
            )
        
        events_created.append(event)
        print(f"✓ Создано мероприятие ID: {event.id}")
    
    print(f"\n=== Готово! Создано {len(events_created)} мероприятий ===")
    print("\nДоступные мероприятия:")
    for event in events_created:
        print(f"  - {event.title} ({event.date_time.strftime('%d.%m.%Y')})")
        print(f"    URL: http://127.0.0.1:8000/event/{event.id}/")
    
    return events_created

if __name__ == '__main__':
    create_test_events()
