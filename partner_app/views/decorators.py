"""Общие декораторы и хелперы для view партнёра."""
from django.shortcuts import redirect
from django.contrib import messages


def check_partner_status(permission_key=None):
    """
    Декоратор для проверки статуса партнёра и прав доступа.
    Если партнёр не одобрен или не имеет нужного права — редирект на дашборд с сообщением.
    """
    def decorator(view_func):
        def wrapper(request, *args, **kwargs):
            if request.user.user_type != "partner":
                return redirect("visitor:dashboard")

            if request.user.verification_status != "approved":
                messages.error(
                    request,
                    "Ваш аккаунт на рассмотрении. Доступ к функционалу ограничен до одобрения администратором."
                )
                return redirect("partner:dashboard")

            if permission_key:
                if not request.user.permissions.get(permission_key, False):
                    messages.error(
                        request,
                        "У вас нет прав для выполнения этого действия. Обратитесь к администратору."
                    )
                    return redirect("partner:dashboard")

            return view_func(request, *args, **kwargs)
        wrapper.__name__ = view_func.__name__
        return wrapper
    return decorator


def get_rejection_messages(request):
    """Возвращает сообщения об отклонении мероприятий для текущего пользователя."""
    from core.models import Event

    rejected_events = Event.objects.filter(organizer=request.user, status="rejected")

    rejection_messages = []
    for event in rejected_events:
        if event.rejection_reason:
            rejection_messages.append(
                f"Мероприятие {event.title} отклонено. Причина: {event.rejection_reason}"
            )

    return rejection_messages
