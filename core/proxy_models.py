"""
Proxy-модели для админки Django.
"""

from django.db import models
from .models import SupportTicket


class EventRequestProxy(SupportTicket):
    """
    Proxy-модель для отображения только заявок на мероприятия в админке.
    """

    class Meta:
        proxy = True
        verbose_name = "Заявка на мероприятие"
        verbose_name_plural = "Заявки на мероприятия"
