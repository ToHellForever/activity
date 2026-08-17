from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse, JsonResponse, HttpResponseBadRequest
from django.utils import timezone
from core.models import Order, Ticket
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth import update_session_auth_hash
from django.views.decorators.http import require_http_methods
from django.views.decorators.clickjacking import xframe_options_exempt
from core.models import (
    Event,
    Ticket,
    Tag,
    SupportTicket,
    SupportMessage,
    SupportAttachment,
    CustomUser,
    Order,
    OrderTicket,
    EventPackage,
    UserPackageSubscription,
)

from django.db import models, transaction, IntegrityError
import logging
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
import uuid
import random
import string
import requests
import json
import base64
import qrcode
import io
from django.core.mail import send_mail
from django.shortcuts import (
    render,
    redirect,
    get_object_or_404,
    HttpResponseRedirect,
    reverse,
)
from django.utils import timezone
from core.tasks import generate_payment_link
from django.contrib.sites.shortcuts import get_current_site
from core.tasks import generate_payment_link

logger = logging.getLogger(__name__)

@login_required
def visitor_dashboard(request):
    # Проверяем тип пользователя
    if request.user.user_type != "visitor":
        # Если зашел партнер, перенаправляем его на его кабинет
        return redirect("partner:dashboard")

    now = timezone.now()

    # Получаем заказы текущего пользователя по email
    all_orders = (
        Order.objects.filter(participant_data__email=request.user.email)
        .exclude(payment_status="canceled")
        .only("id", "participant_data", "created_at", "total_price", "quantity", "attended", "is_paid", "payment_deadline", "payment_status", "purchase_type", "ticket")
        .select_related("ticket", "ticket__event")
        .prefetch_related("tickets")
        .order_by("-created_at")
    )

    # Разделяем на активные и прошедшие
    active_orders = []
    past_orders = []

    for order in all_orders:
        event = order.ticket.event
        is_past = event.date_time < now or order.payment_status == "refunded"

        if is_past:
            past_orders.append(order)
        else:
            active_orders.append(order)

    # Раскрываем каждый заказ на отдельные тикеты (OrderTicket)
    def expand_orders(orders):
        items = []
        for order in orders:
            tickets = order.tickets.all()
            if tickets.exists():
                for ot in tickets:
                    items.append({
                        "order": order,
                        "order_ticket": ot,
                        "event": order.ticket.event,
                        "ticket": order.ticket,
                        "participant_data": order.participant_data,
                    })
            else:
                for i in range(order.quantity):
                    items.append({
                        "order": order,
                        "order_ticket": None,
                        "event": order.ticket.event,
                        "ticket": order.ticket,
                        "participant_data": order.participant_data,
                    })
        return items

    ticket_items = expand_orders(active_orders)
    past_ticket_items = expand_orders(past_orders)

    # Получаем активную подписку пользователя
    user_subscription = (
        UserPackageSubscription.objects.filter(user=request.user, is_active=True)
        .select_related("package")
        .first()
    )

    # Сортируем пакеты от «крутого» к «обычному»
    package_order = {"priority": 0, "extended": 1, "basic": 2}
    packages = sorted(
        EventPackage.objects.all(),
        key=lambda p: package_order.get(p.event_card_type, 99),
    )

    context = {
        "user": request.user,
        "user_orders": active_orders,
        "ticket_items": ticket_items,
        "past_ticket_items": past_ticket_items,
        "past_user_orders": past_orders,
        "now": now,
        "packages": packages,
        "user_subscription": user_subscription,
        "has_active_subscription": user_subscription is not None,
    }
    return render(request, "visitor/dashboard.html", context)

@login_required
def visitor_order_history(request):
    """История заказов — прошедшие мероприятия и возвращённые билеты."""
    if request.user.user_type != "visitor":
        return redirect("visitor:dashboard")

    now = timezone.now()

    past_orders = (
        Order.objects.filter(participant_data__email=request.user.email)
        .exclude(payment_status="canceled")
        .select_related("ticket", "ticket__event")
        .prefetch_related("tickets")
        .order_by("-created_at")
    )

    past_orders = [
        o for o in past_orders
        if o.ticket.event.date_time < now or o.payment_status == "refunded"
    ]

    def expand_orders(orders):
        items = []
        for order in orders:
            tickets = order.tickets.all()
            if tickets.exists():
                for ot in tickets:
                    items.append({
                        "order": order,
                        "order_ticket": ot,
                        "event": order.ticket.event,
                        "ticket": order.ticket,
                        "participant_data": order.participant_data,
                    })
            else:
                for i in range(order.quantity):
                    items.append({
                        "order": order,
                        "order_ticket": None,
                        "event": order.ticket.event,
                        "ticket": order.ticket,
                        "participant_data": order.participant_data,
                    })
        return items

    past_ticket_items = expand_orders(past_orders)

    context = {
        "user": request.user,
        "past_ticket_items": past_ticket_items,
        "past_user_orders": past_orders,
    }
    return render(request, "visitor/order_history.html", context)

@login_required
def settings(request):
    """Страница настроек профиля: отображение данных и смена пароля."""
    
    # Инициализация формы смены пароля
    password_form = None
    
    if request.method == "POST":
        # Проверяем, что запрос именно на смену пароля (можно добавить скрытое поле или проверку префикса имени кнопки)
        if 'change_password' in request.POST:
            password_form = PasswordChangeForm(user=request.user, data=request.POST)
            if password_form.is_valid():
                password_form.save()
                update_session_auth_hash(request, password_form.user)
                messages.success(request, "Пароль успешно изменён!")
                return redirect("visitor:settings") # Перезагружаем страницу, чтобы очистить форму
            # Если форма не валидна, мы продолжим рендерить страницу с ошибками
        else:
            # Здесь можно обработать обновление имени/телефона, если добавите такие формы
            pass
    else:
        password_form = PasswordChangeForm(user=request.user)

    # Получаем данные пользователя для отображения в карточке
    user_data = {
        'name': request.user.get_full_name() or request.user.username,
        'email': request.user.email,
        'phone': getattr(request.user, 'phone', 'Не указан') # Предполагаем, что у модели есть поле phone
    }

    return render(request, "visitor/settings.html", {
        "form": password_form,
        "user_data": user_data,
        "errors": password_form.errors if password_form else {}
    })

@login_required
@require_http_methods(["POST"])
def save_field(request):
    """Сохранение отдельного поля профиля пользователя через AJAX."""
    field_name = request.POST.get("field_name")
    field_value = request.POST.get("field_value")

    if not field_name:
        return JsonResponse({"status": "error", "message": "Не указано поле"}, status=400)

    # Разрешённые поля для редактирования
    allowed_fields = ["name", "phone"]

    if field_name not in allowed_fields:
        return JsonResponse({"status": "error", "message": "Недопустимое поле"}, status=400)

    try:
        if field_name == "name":
            parts = field_value.strip().split()
            if len(parts) >= 2:
                request.user.first_name = parts[0]
                request.user.last_name = parts[-1]
            elif len(parts) == 1:
                request.user.first_name = parts[0]
            request.user.save(update_fields=["first_name", "last_name"])
        elif field_name == "phone":
            request.user.phone = field_value
            request.user.save(update_fields=["phone"])
        return JsonResponse({"status": "success"})
    except Exception as e:
        logger.error(f"Ошибка сохранения поля {field_name}: {e}")
        return JsonResponse({"status": "error", "message": str(e)}, status=500)


def buy_ticket(request, ticket_id=None):
    """
    Страница покупки билета.
    """
    ticket = get_object_or_404(Ticket, id=ticket_id)

    # Если пользователь авторизован, заполняем форму его данными
    initial_data = {}
    if request.user.is_authenticated:
        initial_data = {
            'name': request.user.get_full_name() or request.user.username,
            'email': request.user.email,
            'phone': getattr(request.user, 'phone_number', '')
        }

    context = {
        'ticket': ticket,
        'initial_data': initial_data
    }

    return render(request, 'buy_ticket.html', context)

@login_required
def visitor_chats(request):
    """
    Страница конкретного чата ДЛЯ УЧАСТНИКА.
    Показывает переписку по конкретному билету типа 'participant'.
    """
    selected_ticket = None
    chat_messages = []

    # Фильтруем ТОЛЬКО свои билеты (где я - автор вопроса)
    tickets = SupportTicket.objects.filter(
        user=request.user,
        ticket_type='participant'
    ).order_by("-created_at")

    if request.GET.get("ticket_id"):
        try:
            ticket_id = int(request.GET.get("ticket_id"))
            # Ищем билет, принадлежащий именно этому пользователю
            selected_ticket = get_object_or_404(
                SupportTicket,
                id=ticket_id,
                user=request.user,
                ticket_type='participant'
            )
            # Загружаем сообщения сразу одним запросом
            chat_messages = selected_ticket.messages.all().order_by('created_at')
        except (ValueError, TypeError):
            pass # Некорректный ID или тип данных

    context = {
        "tickets": tickets,
        "selected_ticket": selected_ticket,
        "chat_messages": chat_messages,
    }
    return render(request, "visitor/chats.html", context)


@login_required
def visitor_chats_list(request):
    """
    Страница списка чатов ДЛЯ УЧАСТНИКА.
    Показывает тикеты типа 'participant', которые создал текущий пользователь.
    """
    tickets = SupportTicket.objects.filter(
        user=request.user,
        ticket_type='participant'
    ).order_by("-created_at").select_related('event') # Оптимизация запроса к событию

    # Добавляем последнее сообщение каждому билету "на лету"
    for ticket in tickets:
        # Используем order_by + first() — самый эффективный способ получить один объект
        last_message = ticket.messages.all().order_by('created_at').first()
        setattr(ticket, 'last_message', last_message)

    selected_ticket = None
    
    # Обработка открытия конкретного чата (?ticket_id=...)
    if request.GET.get("ticket_id"):
        try:
            ticket_id = int(request.GET.get("ticket_id"))
            # Проверяем, принадлежит ли этот билет текущему пользователю
            selected_ticket = get_object_or_404(SupportTicket, id=ticket_id, user=request.user)
        except (ValueError, TypeError):
            pass # Если передан некорректный ID, просто игнорируем его

    context = {
        "tickets": tickets,
        "selected_ticket": selected_ticket,
    }
    return render(request, "visitor/chats_list.html", context)

@login_required
@require_http_methods(["GET"])
@xframe_options_exempt
def display_ticket(request, order_id):
    order = get_object_or_404(
        Order.objects.select_related("ticket__event__organizer"),
        id=order_id,
        participant_data__email=request.user.email,
    )
    
    if order.payment_status == "refunded" or not order.is_paid:
        messages.error(request, "Просмотр недоступен.")
        return redirect("visitor:dashboard")

    event = order.ticket.event
    participant = order.participant_data or {}
    place = (event.place_data or {}).get("address", "Место уточняется")
    organizer = event.organizer.get_full_name() or event.organizer.username

    # --- ГЕНЕРАЦИЯ ДАННЫХ QR-КОДОВ ---
    base_url = request.build_absolute_uri('/')[:-1]
    ticket_number_start = getattr(order, 'ticket_number_start', None)
    
    qr_codes = []
    check_link = f"{base_url}{reverse('check_ticket', args=[order.id])}"
    
    for i in range(order.quantity):
        current_ticket_num = (
            ticket_number_start + i 
            if ticket_number_start is not None else f"{order.id}-{i+1}"
        )
        
        data_payload = {
            "order_id": order.id,
            "ticket_id": str(current_ticket_num),
            "event_id": event.id,
            "email": participant.get("email") or "",
        }
        
        qr_img_obj = qrcode.make(json.dumps(data_payload, ensure_ascii=False))
        buffer = io.BytesIO()
        qr_img_obj.save(buffer, format="PNG")
        qr_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')

        qr_codes.append({
            "qr_base64": qr_base64,
            "qr_text": check_link,
            "ticket_number": current_ticket_num,
        })

    context = {
        "order": order,
        "event": event,
        "ticket": order.ticket,
        "participant_name": participant.get("name") or "Участник",
        "email": participant.get("email") or "",
        "price": order.ticket.price,
        "place": place,
        "organizer": organizer,
        "qr_codes": qr_codes,
        "check_link": check_link,
    }

    html = render(request, "visitor/ticket_display.html", context).content.decode("utf-8")
    import re
    body_match = re.search(r'<body[^>]*>(.*?)</body>', html, re.DOTALL | re.IGNORECASE)
    body_html = body_match.group(1) if body_match else html
    return HttpResponse(body_html, content_type="text/html")

@login_required
@require_http_methods(["GET"])
def ticket_qr(request, order_id):
    """Возвращает только PNG QR-код для заказа. QR ведёт на страницу проверки билета."""
    order = get_object_or_404(
        Order.objects.select_related("ticket__event"),
        id=order_id,
        participant_data__email=request.user.email,
    )

    if order.payment_status == "refunded" or not order.is_paid:
        return HttpResponse(status=403)

    from django.urls import reverse
    check_url = f"{request.scheme}://{request.get_host()}{reverse('check_ticket', args=[order.id])}"

    qr = qrcode.QRCode(version=None, box_size=10, border=2)
    qr.add_data(check_url)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="#00056e", back_color="#ffffff").convert("RGB")
    qr_img = qr_img.resize((200, 200))

    buffer = io.BytesIO()
    qr_img.save(buffer, format="PNG")

    response = HttpResponse(buffer.getvalue(), content_type="image/png")
    response["Content-Disposition"] = f'inline; filename="qr_{order.id}.png"'
    return response

