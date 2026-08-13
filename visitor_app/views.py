from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse, JsonResponse, HttpResponseBadRequest
from django.utils import timezone
from core.models import Order, Ticket
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth import update_session_auth_hash
from django.views.decorators.http import require_http_methods
from core.models import (
    Event,
    Ticket,
    Tag,
    SupportTicket,
    SupportMessage,
    SupportAttachment,
    CustomUser,
    Order,
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

    # Получаем заказы текущего пользователя по email
    user_orders = (
        Order.objects.filter(participant_data__email=request.user.email)
        .exclude(payment_status="canceled")
        .only("id", "participant_data", "created_at", "total_price", "quantity", "attended", "is_paid", "payment_deadline", "payment_status", "purchase_type", "ticket")
        .select_related("ticket")
        .prefetch_related("ticket__event")
        .order_by("-created_at")
    )

    logger.info('[dashboard] Заказы для пользователя %s: %d', request.user.email, user_orders.count())

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

    # Логика для посетителя
    context = {
        "user": request.user,
        "user_orders": user_orders,
        "now": timezone.now(),
        "packages": packages,
        "user_subscription": user_subscription,
        "has_active_subscription": user_subscription is not None,
    }
    return render(request, "visitor/dashboard.html", context)

@login_required
def change_password(request):
    """Отдельная страница для смены пароля в личном кабинете посетителя."""
    if request.method == "POST":
        password_form = PasswordChangeForm(user=request.user, data=request.POST)
        if password_form.is_valid():
            password_form.save()
            update_session_auth_hash(request, password_form.user)
            messages.success(request, "Пароль успешно изменён!")
            return redirect("visitor:dashboard")
    else:
        password_form = PasswordChangeForm(user=request.user)

    return render(request, "change_password.html", {"form": password_form})

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
def visitor_event_chats(request):
    """
    Страница участника — показывает чаты по мероприятиям (ticket_type='participant').
    Здесь участник видит вопросы, которые он задавал организаторам через кнопку «Задать вопрос».
    """
    if request.user.user_type != "visitor" and request.user.user_type != "guest":
        return redirect("visitor:dashboard")

    selected_ticket = None
    chat_messages = []

    # Фильтр по статусу
    ticket_filter = request.GET.get("ticket_filter", "all")

    # Показываем ТОЛЬКО participant-тикеты текущего пользователя
    tickets = SupportTicket.objects.filter(
        user=request.user,
        ticket_type='participant'
    ).order_by("-created_at")

    if ticket_filter != "all":
        tickets = tickets.filter(status=ticket_filter)

    if request.GET.get("ticket_id"):
        ticket_id = request.GET.get("ticket_id")
        selected_ticket = get_object_or_404(SupportTicket, id=ticket_id, user=request.user)
        chat_messages = selected_ticket.messages.all()

    context = {
        "tickets": tickets,
        "selected_ticket": selected_ticket,
        "chat_messages": chat_messages,
    }
    return render(request, "visitor/event_chats.html", context)


@login_required
@require_http_methods(["GET"])
def download_ticket(request, order_id):
    """
    Скачивание билета в виде PNG-картинки с QR-кодом.
    Доступно только владельцу заказа: email из participant_data
    должен совпадать с email авторизованного пользователя.
    """
    order = get_object_or_404(
        Order.objects.select_related("ticket__event__organizer"),
        id=order_id,
        participant_data__email=request.user.email,
    )

    if order.payment_status == "refunded":
        messages.error(request, "Билет возвращён — скачивание недоступно.")
        return redirect("visitor:dashboard")

    if not order.is_paid:
        messages.error(request, "Билет ещё не оплачен — скачивание недоступно.")
        return redirect("visitor:dashboard")

    try:
        image = _build_ticket_image(order)
    except Exception:
        logger.exception("Не удалось сформировать билет для заказа %s", order.id)
        messages.error(request, "Не удалось сформировать билет. Попробуйте позже.")
        return redirect("visitor:dashboard")

    buffer = io.BytesIO()
    image.save(buffer, format="PNG")

    response = HttpResponse(buffer.getvalue(), content_type="image/png")
    response["Content-Disposition"] = 'attachment; filename="ticket_{}.png"'.format(order.id)
    return response


def _build_ticket_image(order):
    """Рисует PNG-билет: тёмно-синяя панель слева + QR-код справа."""
    from PIL import Image, ImageDraw, ImageFont

    event = order.ticket.event
    participant = order.participant_data or {}

    # ---------- QR-код ----------
    qr = qrcode.QRCode(version=None, box_size=10, border=2)
    qr.add_data(
        json.dumps(
            {
                "order_id": order.id,
                "ticket_id": order.ticket_id,
                "event_id": event.id,
                "email": participant.get("email") or "",
            },
            ensure_ascii=False,
        )
    )
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="#00056e", back_color="#ffffff").convert("RGB")
    qr_img = qr_img.resize((280, 280))

    W, H = 1200, 660
    DARK = (0, 5, 110)        # #00056e
    ORANGE = (255, 131, 72)   # #ff8348
    GRAY = (119, 122, 141)
    BLACK = (10, 10, 10)

    def _font(size, bold=False):
        path = (
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
            if bold
            else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
        )
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            return ImageFont.load_default()

    def _text_width(text, font):
        try:
            return font.getbbox(text)[2]
        except Exception:
            try:
                return len(text) * font.size
            except Exception:
                return len(text) * 16

    def _wrap(text, font, max_width):
        lines, current = [], ""
        for word in str(text).split():
            candidate = (current + " " + word).strip()
            if _text_width(candidate, font) <= max_width:
                current = candidate
            else:
                if current:
                    lines.append(current)
                current = word
        if current:
            lines.append(current)
        return lines or [""]

    img = Image.new("RGB", (W, H), "#ffffff")
    draw = ImageDraw.Draw(img)

    # Левая синяя панель с оранжевой полосой
    draw.rectangle([0, 0, 470, H], fill=DARK)
    draw.rectangle([462, 0, 470, H], fill=ORANGE)

    title_font = _font(34, bold=True)
    text_font = _font(24)
    small_font = _font(20)
    label_font = _font(17)

    # Название события
    y = 48
    for line in _wrap(event.title, title_font, 400):
        draw.text((48, y), line, fill="#ffffff", font=title_font)
        y += 50
    y += 22

    # Дата и время
    draw.text((48, y), event.date_time.strftime("%d.%m.%Y  %H:%M"), fill=ORANGE, font=text_font)
    y += 52

    # Место проведения
    place = (event.place_data or {}).get("address", "Место уточняется")
    for line in _wrap(place, small_font, 380):
        draw.text((48, y), line, fill="#ffffff", font=small_font)
        y += 34

    # Организатор
    org = event.organizer.get_full_name() or event.organizer.username
    draw.text((48, H - 90), "Организатор", fill=GRAY, font=label_font)
    draw.text((48, H - 62), org, fill="#ffffff", font=small_font)

    # Правая часть — информация о билете
    x = 520
    y = 48
    draw.text((x, y), "БИЛЕТ НА МЕРОПРИЯТИЕ", fill=GRAY, font=label_font)
    y += 44
    draw.text((x, y), "Заказ № {}".format(order.id), fill=BLACK, font=text_font)
    y += 56

    draw.text((x, y), "Тип билета", fill=GRAY, font=label_font)
    y += 30
    draw.text((x, y), order.ticket.name, fill=BLACK, font=text_font)
    y += 56

    draw.text((x, y), "Участник", fill=GRAY, font=label_font)
    y += 30
    name = participant.get("name") or "Участник"
    for line in _wrap(name, text_font, 560):
        draw.text((x, y), line, fill=BLACK, font=text_font)
        y += 38
    y += 12
    draw.text((x, y), participant.get("email") or "", fill=GRAY, font=small_font)
    y += 48

    price = "{}".format(order.total_price).replace(",", " ")
    draw.text((x, y), "Количество: {}".format(order.quantity), fill=BLACK, font=small_font)
    y += 40
    draw.text((x, y), "Итого: {} ₽".format(price), fill=DARK, font=_font(26, bold=True))

    # QR-код в правом нижнем углу
    qx, qy = W - 320, H - 330
    draw.rectangle([qx - 14, qy - 14, qx + 294, qy + 294], outline=ORANGE, width=3)
    img.paste(qr_img, (qx, qy))
    draw.text((qx + 8, qy + 300), "Покажите QR-код на входе", fill=GRAY, font=label_font)

    return img