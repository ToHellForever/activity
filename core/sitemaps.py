"""Django sitemaps для публичных страниц платформы Бизнес Афиша."""
from django.contrib import sitemaps
from django.urls import reverse

from core.models import Event
from venues.models import Venue


class StaticViewSitemap(sitemaps.Sitemap):
    """Карта сайта для статических публичных страниц."""

    changefreq = "monthly"
    priority = 0.5

    def items(self):
        return [
            ("landing_page", "daily", 1.0),
            ("event_list", "daily", 0.9),
            ("venues:venue_list", "daily", 0.9),
            ("about", "monthly", 0.5),
            ("contacts", "monthly", 0.5),
            ("faq", "monthly", 0.5),
        ]

    def location(self, item):
        return reverse(item[0])

    def changefreq(self, item):
        return item[1]

    def priority(self, item):
        return item[2]


class EventSitemap(sitemaps.Sitemap):
    """Карта сайта для активных мероприятий."""

    changefreq = "daily"
    priority = 0.8

    def items(self):
        return Event.objects.filter(status="active").order_by("date_time")

    def location(self, obj):
        return reverse("event_detail", args=[obj.pk])

    def lastmod(self, obj):
        return obj.date_time


class VenueSitemap(sitemaps.Sitemap):
    """Карта сайта для опубликованных площадок."""

    changefreq = "weekly"
    priority = 0.7

    def items(self):
        return Venue.objects.filter(status="published").order_by("-updated_at")

    def location(self, obj):
        return reverse("venues:venue_detail", args=[obj.slug])

    def lastmod(self, obj):
        return obj.updated_at
