#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Скрипт для создания тегов, подтегов и категорий для мероприятий
"""
import os
import sys
import django

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'activity.settings')
django.setup()

from core.models import Event, Tag, MainTag, Category

def create_tags_and_categories():
    print("=== Создание тегов и категорий ===\n")
    
    # Структура тегов и подтегов
    tags_data = {
        'Тематика': [
            'продажи',
            'переговоры',
            'маркетинг',
            'управление',
            'лидерство',
            'HR',
            'финансы',
            'предпринимательство',
            'публичные выступления',
            'личная эффективность',
            'искусственный интеллект',
            'цифровые технологии'
        ],
        'Аудитория': [
            'для предпринимателей',
            'для руководителей',
            'для собственников',
            'для HR',
            'для маркетологов',
            'для специалистов по продажам',
            'для тренеров'
        ],
        'Уровень': [
            'базовый',
            'средний',
            'продвинутый'
        ],
        'Ценность участия': [
            'практика',
            'разбор кейсов',
            'обмен опытом',
            'нетворкинг'
        ]
    }
    
    # Создаём основные теги и подтеги
    main_tags = {}
    all_subtags = {}
    
    for main_name, subtag_names in tags_data.items():
        main_tag, _ = MainTag.objects.get_or_create(name=main_name)
        main_tags[main_name] = main_tag
        print(f"[OK] Основной тег: {main_name}")
        
        subtags = []
        for subtag_name in subtag_names:
            subtag, _ = Tag.objects.get_or_create(name=subtag_name, defaults={'main_tag': main_tag})
            subtags.append(subtag)
            print(f"  OK: {subtag_name}")
        
        all_subtags[main_name] = subtags
    
    # Создаём категории
    categories_data = [
        'Маркетинг',
        'Продажи',
        'Управление',
        'Финансы',
        'IT и Технологии',
        'Лидерство',
        'HR и Кадровое управление',
        'Предпринимательство',
    ]
    
    categories = {}
    for name in categories_data:
        cat, _ = Category.objects.get_or_create(name=name)
        categories[name] = cat
        print(f"[OK] Категория: {name}")
    
    # Получаем все мероприятия
    events = Event.objects.all()
    print(f"\n=== Привязка тегов и категорий к {events.count()} мероприятиям ===\n")
    
    # Распределение подтегов для каждого мероприятия
    for i, event in enumerate(events):
        print(f"--- {event.title} ---")
        
        # Выбираем 5 случайных подтегов из разных групп
        selected_subtags = []
        
        # Берём по 1-2 подтега из каждой группы
        for main_name in list(tags_data.keys())[:4]:
            subtags = all_subtags[main_name]
            # Берём подтег по индексу (циклически)
            idx = (i + len(selected_subtags)) % len(subtags)
            selected_subtags.append(subtags[idx])
            print(f"  + {subtags[idx].name}")
        
        # Привязываем теги
        event.tags.set(selected_subtags)
        
        # Привязываем категорию (циклически)
        cat_names = list(categories.keys())
        event.category = categories[cat_names[i % len(cat_names)]]
        event.save()
        print(f"  + Категория: {event.category.name}")
        
        print()
    
    print("=== Готово! ===")
    print(f"\nСоздано:")
    print(f"  - {len(main_tags)} основных тегов")
    print(f"  - {sum(len(v) for v in all_subtags.values())} подтегов")
    print(f"  - {len(categories)} категорий")
    print(f"  - Привязано к {events.count()} мероприятиям")

if __name__ == '__main__':
    create_tags_and_categories()
