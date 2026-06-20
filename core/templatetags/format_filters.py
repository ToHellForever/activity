#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Темплейт теги для форматирования чисел и цен
"""
from django import template

register = template.Library()


@register.filter(name='format_price')
def format_price(value):
    """
    Форматирует цену с разделением тысяч пробелами.
    
    Пример:
        10000 → 10 000
        15000.50 → 15 000.50
    """
    if value is None:
        return ''
    
    try:
        # Преобразуем в float
        num = float(value)
        
        # Разделяем целую и дробную часть
        integer_part = int(num)
        decimal_part = num - integer_part
        
        # Форматируем целую часть с пробелами
        formatted_integer = "{:,}".format(integer_part).replace(',', ' ')
        
        # Если есть дробная часть, добавляем её
        if decimal_part > 0:
            # Округляем до 2 знаков после запятой
            decimal_str = "{:.2f}".format(decimal_part)[1:]  # включаем точку
            return f"{formatted_integer}{decimal_str}"
        
        return formatted_integer
        
    except (ValueError, TypeError):
        return value


@register.filter(name='any_available')
def any_available(tickets):
    """
    Проверяет, есть ли хотя бы один билет с реальным остатком > 0.
    Использует get_available_count(), который учитывает все незакрытые заказы.
    
    Пример:
        {% with has=tickets|any_available %}
    """
    if not tickets:
        return False
    for ticket in tickets:
        available = getattr(ticket, 'get_available_count', lambda: 0)()
        if available and int(available) > 0:
            return True
    return False


@register.filter(name='format_number')
def format_number(value):
    """
    Форматирует число с разделением тысяч пробелами.
    
    Пример:
        10000 → 10 000
        100 → 100
    """
    if value is None:
        return ''
    
    try:
        num = int(value)
        return "{:,}".format(num).replace(',', ' ')
    except (ValueError, TypeError):
        return value


@register.filter(name='format_duration')
def format_duration(value):
    """
    Форматирует длительность мероприятия из формата 'ЧЧ:ММ' в читаемый вид.
    
    Примеры:
        '01:30' → '1 час 30 мин'
        '02:00' → '2 часа'
        '00:45' → '45 мин'
        '01:00' → '1 час'
        '23:59' → '23 часа 59 мин'
    """
    if not value:
        return ''
    
    try:
        # Парсим строку формата ЧЧ:ММ
        parts = str(value).split(':')
        if len(parts) != 2:
            return value
        
        hours = int(parts[0])
        minutes = int(parts[1])
        
        if hours == 0 and minutes == 0:
            return ''
        
        result = []
        
        # Формируем часы
        if hours > 0:
            if hours % 10 == 1 and hours % 100 != 11:
                result.append(f'{hours} час')
            elif 2 <= hours % 10 <= 4 and not (12 <= hours % 100 <= 14):
                result.append(f'{hours} часа')
            else:
                result.append(f'{hours} часов')
        
        # Формируем минуты
        if minutes > 0:
            if minutes % 10 == 1 and minutes % 100 != 11:
                result.append(f'{minutes} мин')
            elif 2 <= minutes % 10 <= 4 and not (12 <= minutes % 100 <= 14):
                result.append(f'{minutes} минуты')
            else:
                result.append(f'{minutes} мин')
        
        return ' '.join(result)
        
    except (ValueError, AttributeError):
        return value
