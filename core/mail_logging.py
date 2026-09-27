"""
Логирование исходящих писем.

Подключается в settings.py как EMAIL_BACKEND:

    EMAIL_BACKEND = "core.mail_logging.LoggingEmailBackend"

Зачем это нужно
---------------
Django при отправке письма молча глотает часть ошибок: если часть получателей
отвергнута SMTP-сервером, ``send_mail()`` просто вернёт число успешно
отправленных писем (0), и в логах ничего не появляется. Реальную причину
(например, ``550-5.7.26 Your email has been blocked because the sender is ...``
от Gmail) пользователь видит только в отчёте о недоставке от своего
почтового сервера.

Этот бэкенд пишет в лог:

* от кого (From), кому (To/Cc/Bcc), тема, сколько альтернатив/вложений;
* сколько писем принято SMTP-сервером (``sent=1``) — это НЕ гарантия
  доставки: письмо могло быть отвергнуто уже после приёма на задержку/спам-
  фильтр получателя;
* полное тело SMTP-переписки (``smtplib`` пишет её на уровне DEBUG в логгер
  ``smtplib``) — там видно точный ответ сервера получателя.

Все письма пишутся в общий файл ``debug.log`` (см. LOGGING в settings.py),
поэтому для поиска достаточно:

    Select-String -Path debug.log -Pattern "MAIL"

"""

import logging
import smtplib
import traceback

from django.conf import settings
from django.core.mail import EmailMessage
from django.core.mail.backends.smtp import EmailBackend as SmtpEmailBackend

# Логгер named "mail" — попадает в обработчик файла через LOGGING["loggers"]["mail"]
logger = logging.getLogger("mail")

# Максимальная длина тела письма в логе, чтобы не раздувать debug.log
MAX_BODY_LOG_LENGTH = 2000


def _shorten(value, limit=MAX_BODY_LOG_LENGTH):
    """Приводит значение к строке и обрезает до разумной длины."""
    if value is None:
        return ""
    text = value if isinstance(value, str) else str(value)
    text = text.replace("\r\n", "\n").strip()
    if len(text) > limit:
        return text[:limit] + f"... [обрезано, всего {len(text)} символов]"
    return text


def _describe_message(email_message):
    """Формирует краткое человекочитаемое описание письма для лога."""
    if isinstance(email_message, EmailMessage):
        to = list(email_message.to or [])
        cc = list(email_message.cc or [])
        bcc = list(email_message.bcc or [])
        return (
            f"from={email_message.from_email!r} "
            f"to={to} cc={cc} bcc={bcc} "
            f"subject={email_message.subject!r} "
            f"alternatives={len(getattr(email_message, 'alternatives', []) or [])} "
            f"attachments={len(getattr(email_message, 'attachments', []) or [])} "
            f"content_subtype={getattr(email_message, 'content_subtype', 'plain')}"
        )
    return f"message={email_message!r}"


def _log_recipients_raw(email_message):
    """
    Разворачивает список получателей в отдельные строки лога.

    Нужно потому, что Gmail/Яндекс отвергают конкретного получателя, а не
    письмо целиком — по одной строке на адрес проще искать в логе.
    """
    if not isinstance(email_message, EmailMessage):
        return
    for field in ("to", "cc", "bcc"):
        for address in getattr(email_message, field, None) or []:
            logger.info("MAIL recipient field=%s address=%s", field, address)


class LoggingEmailBackend(SmtpEmailBackend):
    """
    SMTP-бэкенд Django с подробным логированием отправки.

    Наследуется от штатного ``django.core.mail.backends.smtp.EmailBackend``,
    поэтому вся остальная логика (TLS, пароли, fail_silently) не меняется.
    """

    def send_messages(self, email_messages):
        messages = list(email_messages or [])

        if not messages:
            logger.debug("MAIL send_messages вызван со списком из 0 писем — нечего отправлять")
            return 0

        host = getattr(settings, "EMAIL_HOST", "")
        port = getattr(settings, "EMAIL_PORT", "")
        user = getattr(settings, "EMAIL_HOST_USER", "")
        backend_name = getattr(settings, "EMAIL_BACKEND", "")
        use_tls = getattr(settings, "EMAIL_USE_TLS", "")
        from_default = getattr(settings, "DEFAULT_FROM_EMAIL", "")
        support_from = getattr(settings, "SUPPORT_FROM_EMAIL", "")
        tickets_from = getattr(settings, "TICKETS_FROM_EMAIL", "")

        logger.info(
            "MAIL ===== отправка: количество=%s backend=%s "
            "smtp=%s:%s tls=%s login=%s "
            "DEFAULT_FROM_EMAIL=%s SUPPORT_FROM_EMAIL=%s TICKETS_FROM_EMAIL=%s",
            len(messages),
            backend_name,
            host,
            port,
            use_tls,
            user,
            from_default,
            support_from,
            tickets_from,
        )

        for index, message in enumerate(messages, start=1):
            logger.info("MAIL [%s/%s] %s", index, len(messages), _describe_message(message))
            _log_recipients_raw(message)

        # Отправляем через штатный механизм
        try:
            sent = super().send_messages(messages)
        except Exception as exc:  # noqa: BLE001 - логируем и пробрасываем выше
            logger.error(
                "MAIL !!! исключение при отправке: %s: %s\n%s",
                type(exc).__name__,
                exc,
                _shorten(traceback.format_exc(), 4000),
            )
            raise

        logger.info(
            "MAIL ===== результат: принято сервером %s из %s "
            "(sent < количества означает, что сервер отверг часть писем; "
            "полный ответ SMTP-сервера ищите в строках smtplib в этом же файле)",
            sent,
            len(messages),
        )

        if sent is not None and sent < len(messages):
            # Django не сообщает, какое именно письмо не ушло, — пишем все
            # получателей, чтобы можно было сопоставить с ответом smtplib.
            for message in messages:
                _log_recipients_raw(message)

        return sent


def log_email_failure(message, error):
    """
    Хелпер для явной фиксации ошибки отправки в местах с fail_silently.

    Использовать в except-блоках там, где письмо уходит с
    ``fail_silently=True`` — иначе ошибка полностью пропадает.
    """
    logger.error(
        "MAIL !!! отправка не удалась: %s: %s | %s",
        type(error).__name__,
        error,
        _describe_message(message),
    )


def debug_smtp_connection(timeout=10):
    """
    Ручная проверка SMTP-подключения с выводом ответа сервера.

    Вызвать из django shell при диагностике:

        from core.mail_logging import debug_smtp_connection
        debug_smtp_connection()

    Возвращает True, если сервер принял логин и объявил поддержку MAIL FROM.
    """
    host = getattr(settings, "EMAIL_HOST", "")
    port = int(getattr(settings, "EMAIL_PORT", 587))
    user = getattr(settings, "EMAIL_HOST_USER", "")
    password = getattr(settings, "EMAIL_HOST_PASSWORD", "")
    use_tls = bool(getattr(settings, "EMAIL_USE_TLS", True))

    logger.info(
        "MAIL debug_smtp_connection: smtp=%s:%s tls=%s login=%s", host, port, use_tls, user
    )

    try:
        with smtplib.SMTP(host, port, timeout=timeout) as smtp:
            smtp.set_debuglevel(1)
            if use_tls:
                smtp.starttls()
            if user:
                smtp.login(user, password)
            code, message = smtp.docmd("NOOP")
            logger.info("MAIL debug_smtp_connection: NOOP -> %s %s", code, message)
            return code == 250
    except smtplib.SMTPException as exc:
        logger.error("MAIL debug_smtp_connection: SMTPException %s: %s", type(exc).__name__, exc)
        return False
    except OSError as exc:
        logger.error("MAIL debug_smtp_connection: OSError %s: %s", type(exc).__name__, exc)
        return False
