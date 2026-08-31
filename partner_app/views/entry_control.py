"""Контроль входа (Entry Control) и мобильный сканер контролёра."""
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.utils import timezone
from django.core.exceptions import ValidationError

from core.models import Event, Order, OrderTicket
from ..models import EventAccessLink


@login_required
def enable_entry_control(request, event_id):
    """
    Организатор создаёт новый код доступа для контролёра.
    Можно создать несколько кодов на одно мероприятие.
    """
    event = get_object_or_404(Event, id=event_id, organizer=request.user)

    if request.method != "POST":
        return JsonResponse({"success": False, "message": "Неверный метод"}, status=405)

    # Проверяем, что мероприятие в активном статусе
    if event.status != "active":
        return JsonResponse(
            {"success": False, "message": "Контроль входа доступен только для активных мероприятий"},
            status=400,
        )

    # Проверяем текущее количество активных ссылок
    active_links_count = EventAccessLink.objects.filter(event=event, is_active=True).count()
    if active_links_count >= EventAccessLink.MAX_ACTIVE_LINKS:
        return JsonResponse({
            "success": False,
            "message": f"Нельзя создать больше {EventAccessLink.MAX_ACTIVE_LINKS} активных ссылок на одно мероприятие. Сейчас уже активно {active_links_count}.",
        }, status=400)

    # Получаем имя контролёра из POST (опционально)
    controller_name = request.POST.get("name", "").strip()

    # Создаём новый код
    try:
        link = EventAccessLink.objects.create(
            event=event,
            name=controller_name,
            is_active=True,
        )
    except ValidationError as e:
        return JsonResponse({
            "success": False,
            "message": e.message,
        }, status=400)

    return JsonResponse({
        "success": True,
        "link_id": link.id,
        "access_code": link.access_code,
        "scanner_url": link.scanner_url,
        "name": link.name,
        "message": "Код доступа создан",
    })


@login_required
def disable_entry_control(request, link_id):
    """
    Организатор отключает конкретный код доступа.
    """
    link = get_object_or_404(EventAccessLink, id=link_id)

    # Проверяем, что мероприятие принадлежит организатору
    if link.event.organizer != request.user:
        return JsonResponse({"success": False, "message": "Нет прав"}, status=403)

    if request.method != "POST":
        return JsonResponse({"success": False, "message": "Неверный метод"}, status=405)

    link.is_active = False
    link.deactivated_at = timezone.now()
    link.save()

    return JsonResponse({
        "success": True,
        "message": "Код доступа отключён",
    })


@login_required
def toggle_entry_control(request, link_id):
    """
    Организатор переключает статус кода (вкл/выкл).
    Проверяем ограничение на количество активных ссылок.
    """
    link = get_object_or_404(EventAccessLink, id=link_id)

    # Проверяем, что мероприятие принадлежит организатору
    if link.event.organizer != request.user:
        return JsonResponse({"success": False, "message": "Нет прав"}, status=403)

    if request.method != "POST":
        return JsonResponse({"success": False, "message": "Неверный метод"}, status=405)

    # Проверяем, что мы включаем ссылку
    if not link.is_active:
        # Считаем текущее количество активных (исключая эту)
        active_count = EventAccessLink.objects.filter(
            event=link.event, is_active=True
        ).exclude(pk=link.pk).count()

        if active_count >= EventAccessLink.MAX_ACTIVE_LINKS:
            return JsonResponse({
                "success": False,
                "message": f"Нельзя активировать больше {EventAccessLink.MAX_ACTIVE_LINKS} ссылок на одно мероприятие. Сейчас уже активно {active_count}.",
            }, status=400)

    link.is_active = not link.is_active
    if link.is_active and not link.activated_at:
        link.activated_at = timezone.now()
    if not link.is_active:
        link.deactivated_at = timezone.now()
    link.save()

    status_msg = "Код активирован" if link.is_active else "Код отключён"
    return JsonResponse({
        "success": True,
        "message": status_msg,
        "is_active": link.is_active,
    })


@login_required
def delete_entry_control(request, link_id):
    """
    Организатор удаляет код доступа.
    """
    link = get_object_or_404(EventAccessLink, id=link_id)

    # Проверяем, что мероприятие принадлежит организатору
    if link.event.organizer != request.user:
        return JsonResponse({"success": False, "message": "Нет прав"}, status=403)

    if request.method != "POST":
        return JsonResponse({"success": False, "message": "Неверный метод"}, status=405)

    link.delete()

    return JsonResponse({
        "success": True,
        "message": "Код доступа удалён",
    })


@login_required
def entry_control_status(request, event_id):
    """
    AJAX: возвращает список всех кодов доступа для мероприятия.
    """
    event = get_object_or_404(Event, id=event_id, organizer=request.user)

    links = EventAccessLink.objects.filter(event=event).order_by("-created_at")

    links_data = []
    total_scanned = 0
    any_active = False
    active_count = 0

    for link in links:
        total_scanned += link.scanned_count
        if link.is_active:
            any_active = True
            active_count += 1
        links_data.append({
            "id": link.id,
            "name": link.name or "Контролёр",
            "access_code": link.access_code,
            "scanner_url": link.scanner_url,
            "is_active": link.is_active,
            "scanned_count": link.scanned_count,
            "created_at": link.created_at.strftime("%d.%m.%Y %H:%M"),
        })

    return JsonResponse({
        "success": True,
        "is_active": any_active,
        "active_count": active_count,
        "total_scanned": total_scanned,
        "links": links_data,
    })


def scanner_view(request, access_code):
    """
    Публичная мобильная страница сканера для контролёра.
    Не требует авторизации — доступ по уникальному коду.
    """
    try:
        link = EventAccessLink.objects.select_related("event").get(
            access_code=access_code
        )
    except EventAccessLink.DoesNotExist:
        return render(request, "partner/scanner_not_found.html")

    event = link.event
    is_active = link.is_active

    # Автоматически деактивируем, если мероприятие завершилось
    if event.ends_at and timezone.now() > event.ends_at:
        link.is_active = False
        link.deactivated_at = timezone.now()
        link.save()
        is_active = False

    context = {
        "event": event,
        "is_active": is_active,
        "access_code": access_code,
        "scanned_count": link.scanned_count,
    }
    return render(request, "partner/scanner.html", context)


@require_POST
def scanner_scan(request, access_code):
    """
    AJAX: проверка билета через сканер.
    Принимает order_id и ticket_number.
    Возвращает JSON с результатом.
    """
    try:
        link = EventAccessLink.objects.select_related("event").get(
            access_code=access_code
        )
    except EventAccessLink.DoesNotExist:
        return JsonResponse(
            {"success": False, "status": "error", "message": "Ссылка не найдена"},
            status=404,
        )

    if not link.is_active:
        return JsonResponse(
            {"success": False, "status": "error", "message": "Контроль входа отключён"},
            status=403,
        )

    order_id = request.POST.get("order_id")
    ticket_number = request.POST.get("ticket_number", 1)

    if not order_id:
        return JsonResponse(
            {"success": False, "status": "error", "message": "Не указан order_id"},
            status=400,
        )

    try:
        order = Order.objects.select_related("ticket__event").get(id=order_id)
    except Order.DoesNotExist:
        return JsonResponse(
            {"success": False, "status": "not_found", "message": "Билет не найден"},
            status=404,
        )

    # Проверяем, что билет относится к правильному мероприятию
    if order.ticket.event != link.event:
        return JsonResponse(
            {"success": False, "status": "error", "message": "Билет не относится к этому мероприятию"},
            status=400,
        )

    # Проверяем валидность билета
    is_valid = (
        order.payment_status == "succeeded"
        and order.is_paid
        and not order.attended
    )

    if not is_valid:
        reason = "Билет недействителен"
        if order.payment_status != "succeeded":
            reason = "Платёж не завершён"
        elif order.attended:
            reason = "Билет уже был использован"
        return JsonResponse({
            "success": True,
            "status": "invalid",
            "message": reason,
            "order_id": order.id,
            "event_title": order.ticket.event.title,
        })

    # Отмечаем билет как посещённый
    try:
        order_ticket = OrderTicket.objects.get(
            order=order,
            ticket_number=int(ticket_number),
        )
        order_ticket.attended = True
        order_ticket.save()
    except OrderTicket.DoesNotExist:
        # Если OrderTicket не найден, пробуем создать
        order_ticket = OrderTicket.objects.create(
            order=order,
            ticket_number=int(ticket_number),
            attended=True,
        )

    # Обновляем общий счётчик заказа
    attended_count = OrderTicket.objects.filter(order=order, attended=True).count()
    total_count = order.quantity

    # Обновляем счётчик заказа
    if attended_count == total_count:
        order.attended = True
        order.save()

    # Обновляем счётчик на ссылке
    link.scanned_count += 1
    link.save()

    participant = order.participant_data
    first_name = participant.get("first_name", "") or participant.get("name", "")
    last_name = participant.get("last_name", "")

    return JsonResponse({
        "success": True,
        "status": "valid",
        "message": "Билет действителен",
        "order_id": order.id,
        "event_title": order.ticket.event.title,
        "ticket_name": order.ticket.name,
        "participant": f"{first_name} {last_name}".strip(),
        "ticket_number": ticket_number,
        "attended_count": attended_count,
        "total_count": total_count,
        "scanned_count": link.scanned_count,
    })


@require_POST
def scanner_end_shift(request, access_code):
    """
    Контролёр завершает смену.
    """
    try:
        link = EventAccessLink.objects.get(access_code=access_code)
    except EventAccessLink.DoesNotExist:
        return JsonResponse(
            {"success": False, "message": "Ссылка не найдена"},
            status=404,
        )

    link.is_active = False
    link.deactivated_at = timezone.now()
    link.save()

    return JsonResponse({
        "success": True,
        "message": f"Смена завершена. Всего отсканировано: {link.scanned_count}",
        "scanned_count": link.scanned_count,
    })
