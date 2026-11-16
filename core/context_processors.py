from django.conf import settings


def unread_badges(request):
    """
    Добавляет в контекст счётчики непрочитанных сообщений для бокового меню:
    unread_support_count и unread_chats_count.
    """
    if not getattr(request, "user", None) or not request.user.is_authenticated:
        return {}

    from core.utils import _get_unread_for_user

    unread_support, unread_chats = _get_unread_for_user(request.user)
    return {
        "unread_support_count": unread_support,
        "unread_chats_count": unread_chats,
    }


def favorite_event_ids(request):
    """
    Добавляет в контекст набор id мероприятий, которые пользователь
    добавил в избранное. Нужен для отрисовки активной иконки избранного
    при загрузке страницы.
    """
    user = getattr(request, "user", None)
    if (
        not user
        or not user.is_authenticated
        or getattr(user, "user_type", "") != "visitor"
    ):
        return {"favorite_event_ids": set()}

    from visitor_app.models import Favorite

    return {
        "favorite_event_ids": set(
            Favorite.objects.filter(user=user).values_list("event_id", flat=True)
        )
    }


def admin_quick_links(request):
    """
    Добавляет быстрые ссылки и API-ключи в контекст для админ-панели.
    """
    return {
        "quick_links": [
            {
                "name": "Дашборд модератора",
                "url": "/moderator/",
                "icon": "📋",
                "description": "Управление обращениями в поддержке",
            },
            {
                "name": "Реестр продаж",
                "url": "/reports/sales-register/",
                "icon": "📊",
                "description": "Отчёт по продажам всех партнёров",
            },
        ],
        "YANDEX_MAPS_API_KEY": getattr(settings, "YANDEX_MAPS_API_KEY", ""),
    }
