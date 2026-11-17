"""Проверка устойчивости страниц к записям фото без файлов."""

import os

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "activity.settings")
django.setup()

from django.db import transaction  # noqa: E402
from django.test import Client  # noqa: E402
from django.utils import timezone  # noqa: E402

from core.models import Event, EventImage  # noqa: E402
from venues.models import Venue, VenueImage  # noqa: E402


class Rollback(Exception):
    pass


try:
    with transaction.atomic():
        venue = Venue.objects.filter(status="published").first()
        VenueImage.objects.filter(venue=venue).delete()
        VenueImage.objects.bulk_create(
            [VenueImage(venue=venue, image="", image_processing_status="done")]
        )

        event = Event.objects.filter(
            status="active", date_time__gte=timezone.now()
        ).first()
        if event is not None:
            EventImage.objects.filter(event=event).delete()
            EventImage.objects.bulk_create(
                [EventImage(event=event, image="", is_primary=True)]
            )

        client = Client()
        urls = ["/", "/venues/", f"/venues/{venue.slug}/"]
        if event is not None:
            urls += ["/events/", f"/events/{event.id}/"]
        for url in urls:
            response = client.get(url, HTTP_HOST="localhost")
            print(url, response.status_code)

        raise Rollback
except Rollback:
    print("rolled back")
