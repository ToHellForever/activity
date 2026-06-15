"""
Proxy-модели для админки Django.
"""

from django.db import models
from .models import SupportTicket, CustomUser


class EventRequestProxy(SupportTicket):
    """
    Proxy-модель для отображения только заявок на мероприятия в админке.
    """

    class Meta:
        proxy = True
        verbose_name = "Заявка на мероприятие"
        verbose_name_plural = "Заявки на мероприятия"


class VisitorUser(CustomUser):
    """
    Proxy-модель для отображения только обычных пользователей (visitor, guest) в админке.
    """
    class Meta:
        proxy = True
        verbose_name = "Обычный пользователь"
        verbose_name_plural = "Обычные пользователи"
