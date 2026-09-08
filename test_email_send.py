"""
Тестовый скрипт для проверки отправки email через Django.

Запуск:
    python test_email_send.py
"""

import os
import sys
import logging

# Добавляем проект в путь
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Загружаем настройки Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "activity.settings")

import django
django.setup()

from django.core.mail import send_mail, EmailMultiAlternatives
from django.conf import settings
from django.template.loader import render_to_string
import traceback

# --- Логирование ---
logger = logging.getLogger("email_test")
logger.setLevel(logging.DEBUG)

# Консольный хендлер
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.DEBUG)
formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

# Файловый хендлер
file_handler = logging.FileHandler(os.path.join(os.path.dirname(__file__), "email_test.log"), encoding="utf-8")
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)


def check_settings():
    """Проверяет текущие настройки email и выводит их."""
    logger.info("=" * 60)
    logger.info("ПРОВЕРКА НАСТРОЕК EMAIL")
    logger.info("=" * 60)
    logger.info(f"EMAIL_BACKEND:     {settings.EMAIL_BACKEND}")
    logger.info(f"EMAIL_HOST:        {settings.EMAIL_HOST}")
    logger.info(f"EMAIL_PORT:        {settings.EMAIL_PORT}")
    logger.info(f"EMAIL_USE_TLS:     {settings.EMAIL_USE_TLS}")
    logger.info(f"EMAIL_HOST_USER:   {settings.EMAIL_HOST_USER}")
    logger.info(f"EMAIL_HOST_PASSWORD: {'*' * len(settings.EMAIL_HOST_PASSWORD)}")
    logger.info(f"DEFAULT_FROM_EMAIL:{settings.DEFAULT_FROM_EMAIL}")

    # Проверяем, что значения пришли из .env
    from dotenv import dotenv_values
    env_values = dotenv_values(os.path.join(os.path.dirname(__file__), ".env"))
    logger.info("\nЗначения из .env файла:")
    for key in ["EMAIL_BACKEND", "EMAIL_HOST", "EMAIL_PORT", "EMAIL_USE_TLS",
                "EMAIL_HOST_USER", "EMAIL_HOST_PASSWORD", "DEFAULT_FROM_EMAIL"]:
        env_val = env_values.get(key, "<NOT SET>")
        logger.info(f"  {key}: {env_val}")


def test_send_simple():
    """Отправляет простое тестовое письмо."""
    logger.info("\n" + "=" * 60)
    logger.info("ТЕСТ 1: Простое письмо через send_mail")
    logger.info("=" * 60)

    try:
        result = send_mail(
            subject="[TEST] Тестовое сообщение от Activity",
            message="Это тестовое сообщение. Если вы его получили - email настроен правильно!",
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=["dim.anosoff2018@yandex.ru"],
            fail_silently=False,
        )
        logger.info(f"Результат: отправлено писем = {result}")
        logger.info("OK ТЕСТ 1 ПРОЙДЕН!")
    except Exception as e:
        logger.error(f"ERROR ТЕСТ 1 ПРОВАЛЕН!")
        logger.error(f"Ошибка: {e}")
        logger.error(traceback.format_exc())


def test_send_html():
    """Отправляет письмо с HTML-контентом."""
    logger.info("\n" + "=" * 60)
    logger.info("ТЕСТ 2: HTML письмо через EmailMessage")
    logger.info("=" * 60)

    try:
        html_message = render_to_string("emails/test_email.html", {
            "title": "Тестовое сообщение",
            "message": "Это HTML-версия тестового письма. Если вы видите форматированный текст - всё работает!",
        })

        email = EmailMultiAlternatives(
            subject="[TEST] HTML тестовое сообщение",
            body="Это текстовая версия письма. Если ваш клиент не поддерживает HTML, вы видите этот текст.",
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=["dim.anosoff2018@yandex.ru"],
        )
        email.attach_alternative(html_message, "text/html")
        email.send(fail_silently=False)

        logger.info("OK ТЕСТ 2 ПРОЙДЕН!")
    except Exception as e:
        logger.error(f"ERROR ТЕСТ 2 ПРОВАЛЕН!")
        logger.error(f"Ошибка: {e}")
        logger.error(traceback.format_exc())


def test_send_connection():
    """Проверяет подключение к SMTP-серверу."""
    logger.info("\n" + "=" * 60)
    logger.info("ТЕСТ 3: Проверка подключения к SMTP")
    logger.info("=" * 60)

    try:
        from django.core.mail.backends.smtp import EmailBackend
        backend = EmailBackend(
            host=settings.EMAIL_HOST,
            port=settings.EMAIL_PORT,
            username=settings.EMAIL_HOST_USER,
            password=settings.EMAIL_HOST_PASSWORD,
            use_tls=settings.EMAIL_USE_TLS,
            fail_silently=False,
        )
        backend.open()
        logger.info("OK Подключение к SMTP успешно!")
        backend.close()
        logger.info("OK ТЕСТ 3 ПРОЙДЕН!")
    except Exception as e:
        logger.error(f"ERROR ТЕСТ 3 ПРОВАЛЕН!")
        logger.error(f"Ошибка подключения к SMTP: {e}")
        logger.error(traceback.format_exc())


if __name__ == "__main__":
    logger.info("Начинаем тестирование email...\n")

    # Шаг 1: Проверяем настройки
    check_settings()

    # Шаг 2: Проверяем подключение к SMTP
    test_send_connection()

    # Шаг 3: Отправляем простое письмо
    test_send_simple()

    # Шаг 4: Отправляем HTML письмо
    test_send_html()

    logger.info("\n" + "=" * 60)
    logger.info("ТЕСТИРОВАНИЕ ЗАВЕРШЕНО")
    logger.info("=" * 60)
    logger.info("Логи сохранены в: email_test.log")
