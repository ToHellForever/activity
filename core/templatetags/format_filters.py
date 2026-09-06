#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Темплейт теги для форматирования чисел и цен
"""
import re
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


@register.filter(name='format_coordinate')
def format_coordinate(value):
    """
    Форматирует координату для использования в URL карт и API,
    используя точку как десятичный разделитель.
    """
    if value is None:
        return ''

    try:
        text = str(value).strip()
        if ',' in text and '.' not in text:
            text = text.replace(',', '.')
        return f"{float(text):.6f}".replace(',', '.')
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


@register.filter(name='dict_get')
def dict_get(dictionary, key):
    """
    Получает значение из словаря по ключу в шаблоне Django.
    
    Пример:
        {{ ticket_sold_counts|dict_get:item.pk }}
    """
    if not dictionary:
        return 0
    try:
        return dictionary.get(key, 0)
    except (AttributeError, TypeError):
        return 0


@register.filter(name='auto_format')
def auto_format(text):
    """
    Автоматически форматирует обычный текст в HTML:
    - Если есть **жирный**, - списки, заголовки с : → применяем продвинутое форматирование
    - Иначе → просто оборачиваем в <p> с переносами строк
    """
    if not text:
        return ''
    
    from django.utils.html import escape as html_escape
    from django.utils.safestring import mark_safe
    from django.template.defaultfilters import linebreaks
    
    text = html_escape(text)
    
    # Проверяем, есть ли продвинутое форматирование
    has_advanced = ('**' in text or '__' in text or 
                    re.search(r'^[-*]\s+', text, re.MULTILINE) or
                    re.search(r'^\d+\.\s+', text, re.MULTILINE))
    
    if has_advanced:
        return _advanced_format(text, mark_safe, re, apply_inline_formatting)
    
    # Простой текст — оборачиваем в абзацы
    return mark_safe(linebreaks(text))


def _advanced_format(text, mark_safe, re, apply_inline_formatting):
    """Продвинутое форматирование: заголовки, списки, жирный/курсив."""
    lines = text.split('\n')
    result = []
    in_list = None
    in_paragraph = False
    
    for line in lines:
        stripped = line.strip()
        
        # Пустая строка — закрываем текущий блок
        if not stripped:
            if in_list:
                result.append(f'</{in_list}>')
                in_list = None
            if in_paragraph:
                result.append('</p>')
                in_paragraph = False
            continue
        
        # Разделитель
        if re.match(r'^[-*_]{3,}$', stripped):
            if in_list:
                result.append(f'</{in_list}>')
                in_list = None
            if in_paragraph:
                result.append('</p>')
                in_paragraph = False
            result.append('<hr>')
            continue
        
        # Заголовок: жирный текст + двоеточие
        if re.match(r'^\*\*[^*]+\*\*:$', stripped) or re.match(r'^__[^_]+__:$', stripped):
            if in_list:
                result.append(f'</{in_list}>')
                in_list = None
            if in_paragraph:
                result.append('</p>')
                in_paragraph = False
            heading = re.sub(r'\*\*([^*]+)\*\*', r'<b>\1</b>', stripped)
            heading = re.sub(r'__([^_]+)__', r'<b>\1</b>', heading)
            result.append(f'<h3>{heading}</h3>')
            continue
        
        # Маркированный список
        bullet_match = re.match(r'^[-*]\s+(.+)$', stripped)
        if bullet_match:
            if in_list is None:
                result.append('<ul>')
                in_list = 'ul'
            item = apply_inline_formatting(bullet_match.group(1))
            result.append(f'<li>{item}</li>')
            continue
        
        # Нумерованный список
        numbered_match = re.match(r'^\d+\.\s+(.+)$', stripped)
        if numbered_match:
            if in_list is None:
                result.append('<ol>')
                in_list = 'ol'
            item = apply_inline_formatting(numbered_match.group(1))
            result.append(f'<li>{item}</li>')
            continue
        
        # Закрываем список если был
        if in_list:
            result.append(f'</{in_list}>')
            in_list = None
        
        # Обычная строка — абзац
        if not in_paragraph:
            result.append('<p>')
            in_paragraph = True
        else:
            result.append('<br>')
        result.append(apply_inline_formatting(stripped))
    
    if in_list:
        result.append(f'</{in_list}>')
    if in_paragraph:
        result.append('</p>')
    
    return mark_safe(''.join(result))


def apply_inline_formatting(text):
    """Применяет форматирование внутри строки: жирный, курсив, ссылки."""
    # Жирный: **текст** или __текст__
    text = re.sub(r'\*\*([^*]+)\*\*', r'<b>\1</b>', text)
    text = re.sub(r'__([^_]+)__', r'<b>\1</b>', text)
    # Курсив: *текст* или _текст_
    text = re.sub(r'\*([^*]+)\*', r'<i>\1</i>', text)
    text = re.sub(r'(?<!\w)_([^_]+)_(?!\w)', r'<i>\1</i>', text)
    return text
