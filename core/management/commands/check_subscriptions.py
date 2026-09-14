"""Проверка и обслуживание подписок на пакеты вручную.

Позволяет увидеть, как Celery-задача обслуживает подписки:
истёкшие деактивируются, запланированные смены применяются.

Использование:
    python manage.py check_subscriptions                 # показать состояние
    python manage.py check_subscriptions --user email    # фильтр по пользователю
    python manage.py check_subscriptions --run           # выполнить обработку
    python manage.py check_subscriptions --run --user email
"""
from django.core.management.base import BaseCommand
from django.utils import timezone

from core.models import UserPackageSubscription
from core.tasks import check_and_apply_scheduled_package_changes


class Command(BaseCommand):
    help = "Показывает состояние подписок и опционально запускает их обслуживание"

    def add_arguments(self, parser):
        parser.add_argument(
            "--user",
            type=str,
            default=None,
            help="Email пользователя для фильтрации",
        )
        parser.add_argument(
            "--run",
            action="store_true",
            help="Запустить обработку (как Celery-задача)",
        )

    def handle(self, *args, **options):
        user_email = options["user"]
        run = options["run"]

        queryset = UserPackageSubscription.objects.select_related(
            "user", "package", "scheduled_change_to"
        ).order_by("user__email", "-start_date")
        if user_email:
            queryset = queryset.filter(user__email=user_email)

        now = timezone.now()

        self.stdout.write("")
        self.stdout.write(
            self.style.MIGRATE_HEADING(
                f"Подписки (сейчас: {now:%d.%m.%Y %H:%M:%S})"
            )
        )

        active_count = 0
        for subscription in queryset:
            if subscription.is_active:
                active_count += 1
            days_left = (
                subscription.end_date - now
            ).total_seconds() / 86400 if subscription.end_date else None

            if not subscription.is_active:
                status = self.style.ERROR("НЕАКТИВНА")
            elif days_left is not None and days_left <= 0:
                # Активна в БД, но время вышло — задача это исправит
                status = self.style.WARNING("ИСТЕКЛА (ждёт задачи)")
            else:
                status = self.style.SUCCESS(
                    f"АКТИВНА (осталось {days_left:.1f} дн.)"
                )

            scheduled = ""
            if subscription.scheduled_change_to:
                scheduled = (
                    f" | смена на «{subscription.scheduled_change_to.name}» "
                    f"с {subscription.scheduled_change_date:%d.%m.%Y %H:%M}"
                )

            self.stdout.write(
                f"  [{subscription.pk}] {subscription.user.email}: "
                f"«{subscription.package.name}» "
                f"до {subscription.end_date:%d.%m.%Y %H:%M} — {status}{scheduled}"
            )

        if not queryset.exists():
            self.stdout.write("  (подписок не найдено)")

        self.stdout.write("")
        self.stdout.write(f"Активных подписок: {active_count}")

        if run:
            self.stdout.write("")
            self.stdout.write(self.style.MIGRATE_HEADING("Запуск обработки..."))
            result = check_and_apply_scheduled_package_changes()
            self.stdout.write(self.style.SUCCESS(f"Результат: {result}"))
            self.stdout.write(
                "Повторите команду без --run, чтобы увидеть новое состояние."
            )
        elif any(
            not s.is_active and s.end_date and s.end_date <= now
            for s in queryset
        ):
            self.stdout.write("")
            self.stdout.write(
                self.style.WARNING(
                    "Есть истёкшие подписки, которые ещё числятся активными. "
                    "Запустите: python manage.py check_subscriptions --run "
                    "(или дождитесь Celery-задачи, она выполняется каждые 5 минут)."
                )
            )
