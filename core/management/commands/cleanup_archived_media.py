# -*- coding: utf-8 -*-
"""
Команда ручной очистки медиа архивных мероприятий.

Запуск:
    python manage.py cleanup_archived_media            # dry-run: только показать
    python manage.py cleanup_archived_media --run      # выполнить очистку
    python manage.py cleanup_archived_media --days 90  # свой порог (дней)

По умолчанию ничего не удаляется — без --run команда работает в режиме
предпросмотра и лишь показывает, что будет удалено.
"""

from django.core.management.base import BaseCommand
from django.conf import settings
from django.utils import timezone

from core.models import Event
from core.tasks import _clean_single_event_media, _send_media_cleanup_notification


class Command(BaseCommand):
    help = "Очищает медиа архивных мероприятий (completed/on_moderation/rejected по дате; active не трогает)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--run",
            action="store_true",
            help="Выполнить удаление. Без этого флага — только предпросмотр.",
        )
        parser.add_argument(
            "--days",
            type=int,
            default=None,
            help="Порог в днях (по умолчанию ARCHIVED_EVENT_MEDIA_RETENTION_DAYS).",
        )
        parser.add_argument(
            "--notify",
            action="store_true",
            help="Отправить организаторам дайджест-письма после очистки.",
        )

    def handle(self, *args, **options):
        do_run = options["run"]
        notify = options["notify"] and do_run
        retention_days = (
            settings.ARCHIVED_EVENT_MEDIA_RETENTION_DAYS
            if options["days"] is None
            else options["days"]
        )
        cutoff = timezone.now() - timezone.timedelta(days=retention_days)

        events = (
            Event.objects.filter(
                status__in=["completed", "on_moderation", "rejected"],
                date_time__lte=cutoff,
            )
            .select_related("organizer")
            .order_by("date_time")
        )

        mode = "ВЫПОЛНЕНИЕ" if do_run else "ПРЕДПРОСМОТР (без --run)"
        self.stdout.write(self.style.WARNING(f"=== {mode} ==="))
        self.stdout.write(
            f"Порог: мероприятия старше {retention_days} дней "
            f"(дата <= {timezone.localtime(cutoff):%d.%m.%Y})"
        )
        self.stdout.write(f"Найдено мероприятий: {events.count()}\n")

        total = {"events": 0, "photos": 0, "videos": 0, "programs": 0}
        by_organizer = {}
        organizers_map = {}

        for event in events:
            # Считаем, что будет удалено, без записи в БД (для предпросмотра).
            gallery = list(event.images.order_by("-is_primary", "id"))
            photos_to_delete = max(len(gallery) - 1, 0)
            has_video = bool(event.video_url)
            has_program = bool(event.program_file)

            if not (photos_to_delete or has_video or has_program):
                continue

            total["events"] += 1
            total["photos"] += photos_to_delete
            total["videos"] += int(has_video)
            total["programs"] += int(has_program)

            self.stdout.write(
                f"[{event.pk}] {event.title} "
                f"({timezone.localtime(event.date_time):%d.%m.%Y}): "
                f"фото к удалению {photos_to_delete}, "
                f"видео {'да' if has_video else 'нет'}, "
                f"программа {'да' if has_program else 'нет'}"
            )

            if do_run:
                try:
                    stats = _clean_single_event_media(event)
                    by_organizer.setdefault(event.organizer_id, []).append(stats)
                    organizers_map[event.organizer_id] = event.organizer
                except Exception as e:
                    self.stderr.write(
                        self.style.ERROR(f"  ошибка обработки {event.pk}: {e}")
                    )

        self.stdout.write("\n" + self.style.SUCCESS("=== Итого ==="))
        self.stdout.write(
            f"Мероприятий: {total['events']}, "
            f"фото: {total['photos']}, "
            f"видео: {total['videos']}, "
            f"программ: {total['programs']}"
        )

        if not do_run:
            self.stdout.write(
                self.style.WARNING(
                    "\nНичего не удалено. Для выполнения добавьте --run."
                )
            )
            return

        if notify:
            for organizer_id, cleaned in by_organizer.items():
                _send_media_cleanup_notification(
                    organizers_map.get(organizer_id), cleaned
                )
            self.stdout.write(
                self.style.SUCCESS(f"Отправлено уведомлений: {len(by_organizer)}")
            )
        else:
            self.stdout.write(
                self.style.SUCCESS("Очистка выполнена (уведомления: --notify).")
            )
