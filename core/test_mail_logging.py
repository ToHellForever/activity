import ssl
from unittest.mock import Mock, call, patch

from django.core.mail import EmailMessage
from django.test import SimpleTestCase, override_settings

from core.mail_logging import LoggingEmailBackend


@override_settings(
    EMAIL_HOST="smtp.yandex.ru",
    EMAIL_PORT=587,
    EMAIL_USE_TLS=True,
    EMAIL_USE_SSL=False,
    EMAIL_TIMEOUT=5,
    EMAIL_HOST_USER="sender@yandex.ru",
    EMAIL_HOST_PASSWORD="yandex-password",
    MAILRU_EMAIL="sender@mail.ru",
    MAILRU_APP_PASSWORD="mailru-password",
    MAILRU_EMAIL_HOST="smtp.mail.ru",
    MAILRU_EMAIL_PORT=465,
    MAILRU_EMAIL_USE_TLS=False,
    MAILRU_EMAIL_USE_SSL=True,
    MAILRU_EMAIL_TIMEOUT=5,
)
class LoggingEmailBackendTestCase(SimpleTestCase):
    def test_smtp_context_uses_trusted_certificates_with_verification_enabled(self):
        context = LoggingEmailBackend.VerifiedSmtpEmailBackend().ssl_context

        self.assertEqual(context.verify_mode, ssl.CERT_REQUIRED)
        self.assertTrue(context.check_hostname)
        self.assertTrue(context.get_ca_certs())

    @patch("core.mail_logging.LoggingEmailBackend.VerifiedSmtpEmailBackend")
    def test_uses_mailru_after_primary_smtp_failure(self, smtp_backend):
        primary = Mock()
        primary.send_messages.side_effect = TimeoutError("SMTP timeout")
        backup = Mock()
        backup.send_messages.return_value = 1
        smtp_backend.side_effect = [primary, backup]

        message = EmailMessage(
            "Subject",
            "Body",
            "sender@yandex.ru",
            ["recipient@example.com"],
        )

        sent = LoggingEmailBackend().send_messages([message])

        self.assertEqual(sent, 1)
        self.assertEqual(smtp_backend.call_count, 2)
        self.assertEqual(
            smtp_backend.call_args_list,
            [
                call(
                    host="smtp.yandex.ru",
                    port=587,
                    username="sender@yandex.ru",
                    password="yandex-password",
                    use_tls=True,
                    use_ssl=False,
                    timeout=5,
                    fail_silently=False,
                ),
                call(
                    host="smtp.mail.ru",
                    port=465,
                    username="sender@mail.ru",
                    password="mailru-password",
                    use_tls=False,
                    use_ssl=True,
                    timeout=5,
                    fail_silently=False,
                ),
            ],
        )
        self.assertEqual(backup.send_messages.call_args.args[0][0].from_email, "sender@mail.ru")
        self.assertEqual(message.from_email, "sender@yandex.ru")

    @patch("core.mail_logging.LoggingEmailBackend.VerifiedSmtpEmailBackend")
    def test_does_not_use_mailru_when_primary_succeeds(self, smtp_backend):
        primary = Mock()
        primary.send_messages.return_value = 1
        smtp_backend.return_value = primary

        message = EmailMessage(
            "Subject",
            "Body",
            "sender@yandex.ru",
            ["recipient@example.com"],
        )

        self.assertEqual(LoggingEmailBackend().send_messages([message]), 1)
        self.assertEqual(smtp_backend.call_count, 1)

    @override_settings(MAILRU_EMAIL="", MAILRU_APP_PASSWORD="")
    @patch("core.mail_logging.LoggingEmailBackend.VerifiedSmtpEmailBackend")
    def test_raises_primary_error_when_fallback_is_not_configured(self, smtp_backend):
        primary = Mock()
        primary.send_messages.side_effect = TimeoutError("SMTP timeout")
        smtp_backend.return_value = primary

        message = EmailMessage(
            "Subject",
            "Body",
            "sender@yandex.ru",
            ["recipient@example.com"],
        )

        with self.assertRaisesRegex(TimeoutError, "SMTP timeout"):
            LoggingEmailBackend().send_messages([message])

        self.assertEqual(smtp_backend.call_count, 1)
