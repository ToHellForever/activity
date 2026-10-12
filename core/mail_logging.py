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
import ssl
import traceback
from copy import copy
from functools import cached_property

import certifi
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
    SMTP-бэкенд Django с подробным логированием и резервной отправкой через Mail.ru.

    Каждое письмо сначала отправляется через основной SMTP-сервер. При ошибке
    отправки письмо повторяется через Mail.ru, если заданы его учётные данные.
    """

    class VerifiedSmtpEmailBackend(SmtpEmailBackend):
        @cached_property
        def ssl_context(self):
            context = ssl.create_default_context(cafile=certifi.where())
            if self.ssl_certfile or self.ssl_keyfile:
                context.load_cert_chain(self.ssl_certfile, self.ssl_keyfile)
            return context

    @staticmethod
    def _smtp_backend(host, port, username, password, use_tls, use_ssl, timeout):
        return LoggingEmailBackend.VerifiedSmtpEmailBackend(
            host=host,
            port=port,
            username=username,
            password=password,
            use_tls=use_tls,
            use_ssl=use_ssl,
            timeout=timeout,
            fail_silently=False,
        )

    @staticmethod
    def _mailru_is_configured():
        return bool(
            getattr(settings, "MAILRU_EMAIL", "")
            and getattr(settings, "MAILRU_APP_PASSWORD", "")
        )

    def _send_via_mailru(self, message):
        backup_message = copy(message)
        backup_message.from_email = settings.MAILRU_EMAIL
        backend = self._smtp_backend(
            host=settings.MAILRU_EMAIL_HOST,
            port=settings.MAILRU_EMAIL_PORT,
            username=settings.MAILRU_EMAIL,
            password=settings.MAILRU_APP_PASSWORD,
            use_tls=settings.MAILRU_EMAIL_USE_TLS,
            use_ssl=settings.MAILRU_EMAIL_USE_SSL,
            timeout=settings.MAILRU_EMAIL_TIMEOUT,
        )
        return backend.send_messages([backup_message])

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

        sent = 0
        for index, message in enumerate(messages, start=1):
            if not message.recipients():
                logger.warning(
                    "MAIL [%s/%s] письмо пропущено: нет получателей",
                    index,
                    len(messages),
                )
                continue

            primary = self._smtp_backend(
                host=settings.EMAIL_HOST,
                port=settings.EMAIL_PORT,
                username=settings.EMAIL_HOST_USER,
                password=settings.EMAIL_HOST_PASSWORD,
                use_tls=settings.EMAIL_USE_TLS,
                use_ssl=getattr(settings, "EMAIL_USE_SSL", False),
                timeout=getattr(settings, "EMAIL_TIMEOUT", 5),
            )
            try:
                primary_sent = primary.send_messages([message])
                if primary_sent:
                    sent += primary_sent
                    continue
                primary_error = RuntimeError("Основной SMTP-сервер не принял письмо")
            except (smtplib.SMTPException, OSError) as exc:
                primary_error = exc

            logger.error(
                "MAIL !!! основной SMTP-сервер не отправил письмо [%s/%s]: %s: %s\n%s",
                index,
                len(messages),
                type(primary_error).__name__,
                primary_error,
                _shorten("".join(traceback.format_exception(primary_error)), 4000),
            )

            if not self._mailru_is_configured():
                logger.error(
                    "MAIL !!! резерв Mail.ru не настроен: "
                    "задайте MAILRU_EMAIL и MAILRU_APP_PASSWORD"
                )
                if not self.fail_silently:
                    raise primary_error
                continue

            try:
                backup_sent = self._send_via_mailru(message)
            except (smtplib.SMTPException, OSError) as backup_error:
                logger.error(
                    "MAIL !!! резервный SMTP Mail.ru также не отправил письмо [%s/%s]: %s: %s\n%s",
                    index,
                    len(messages),
                    type(backup_error).__name__,
                    backup_error,
                    _shorten("".join(traceback.format_exception(backup_error)), 4000),
                )
                if not self.fail_silently:
                    raise backup_error from primary_error
                continue

            sent += backup_sent
            logger.info(
                "MAIL ===== письмо [%s/%s] отправлено через резерв Mail.ru (sent=%s)",
                index,
                len(messages),
                backup_sent,
            )

        logger.info("MAIL ===== результат: принято SMTP-серверами %s из %s писем", sent, len(messages))
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
