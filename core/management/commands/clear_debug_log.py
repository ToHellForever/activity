"""
Очистка дебаг-лога (debug.log).

Использование:
    python manage.py clear_debug_log

Лог усекается до нуля, а не удаляется: пока запущен dev-сервер,
logging.FileHandler держит файл открытым, и удаление на Windows
приведёт к ошибке или продолжению записи в «осиротевший» файл.
"""
import logging
import os

from django.conf import settings
from django.core.management.base import BaseCommand


def _get_log_path():
    """
    Достаёт путь к файлу лога из LOGGING (первый FileHandler).
    Если не найден — возвращает debug.log в корне проекта.
    """
    handlers = settings.LOGGING.get("handlers", {}) if hasattr(settings, "LOGGING") else {}
    for handler in handlers.values():
        if handler.get("class", "").endswith("FileHandler") and "filename" in handler:
            return handler["filename"]
    return os.path.join(settings.BASE_DIR, "debug.log")


class Command(BaseCommand):
    help = "Очищает дебаг-лог (debug.log), не удаляя сам файл."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Показать размер лога, ничего не удаляя.",
        )

    def handle(self, *args, **options):
        log_path = _get_log_path()

        if not os.path.exists(log_path):
            self.stdout.write(self.style.WARNING(f"Лог не найден: {log_path}"))
            return

        size = os.path.getsize(log_path)
        self.stdout.write(f"Лог: {log_path} ({self._fmt_size(size)})")

        if options["dry_run"]:
            self.stdout.write("Режим dry-run: файл не изменён.")
            return

        if size == 0:
            self.stdout.write(self.style.WARNING("Лог уже пуст."))
            return

        try:
            # Открываем в режиме 'r+' (не 'w'), чтобы не пересоздавать файл:
            # так сохраняются права и дескриптор остаётся валидным для сервера.
            with open(log_path, "r+", encoding="utf-8", errors="ignore") as f:
                f.truncate(0)
        except PermissionError:
            # Файл занят (например, запущен runserver) — пробуем усечь без открытия
            try:
                os.truncate(log_path, 0)
            except OSError as e:
                raise CommandError(
                    f"Не удалось очистить лог (файл занят?): {e}. "
                    f"Остановите dev-сервер и повторите."
                )

        self.stdout.write(self.style.SUCCESS(
            f"Лог очищен, освобождено {self._fmt_size(size)}."
        ))

    @staticmethod
    def _fmt_size(num_bytes):
        for unit in ("Б", "КБ", "МБ", "ГБ"):
            if num_bytes < 1024 or unit == "ГБ":
                return f"{num_bytes:.1f} {unit}"
            num_bytes /= 1024
