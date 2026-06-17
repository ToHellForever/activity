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
