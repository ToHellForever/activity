from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
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
        .select_related("ticket__event")
        .order_by("-created_at")
    )

    # Логика для посетителя
    context = {"user": request.user, "user_orders": user_orders, "now": timezone.now()}
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


@login_required
def refund_ticket(request, order_id):
    """
    Обработка возврата билета.
    """
    order = get_object_or_404(
        Order, id=order_id, participant_data__email=request.user.email
    )

    # Проверяем, можно ли вернуть билет
    refund_deadline = order.ticket.event.get_refund_deadline()
    if refund_deadline <= timezone.now():
        messages.error(request, "Срок возврата билета истёк.")
        return redirect("visitor:dashboard")

    # Обновляем статус заказа на "возврат"
    order.payment_status = "refunded"
    order.save()

    messages.success(request, "Билет успешно возвращён. Статус заказа обновлён.")
    return redirect("visitor:dashboard")


@csrf_exempt
def yookassa_webhook(request):
    # Логируем все входящие данные (для отладки)
    logger.info(f"Webhook received. Method: {request.method}")
    logger.info(f"Headers: {request.headers}")
    logger.info(
        f"Body: {request.body.decode('utf-8') if request.body else 'Empty body'}"
    )

    # Проверяем метод запроса
    if request.method != "POST":
        logger.warning("Non-POST request received")
        return HttpResponseBadRequest("Only POST allowed")

    # Парсим JSON
    try:
        event_json = json.loads(request.body)
        logger.info(f"Parsed event: {event_json}")
    except json.JSONDecodeError:
        logger.error("Invalid JSON format")
        return HttpResponseBadRequest("Invalid JSON")

    # Проверяем тип уведомления
    if event_json.get("type") != "notification":
        logger.warning(f"Not a notification type: {event_json.get('type')}")
        return HttpResponseBadRequest("Not a notification")

    # Обрабатываем событие
    try:
        event = event_json["event"]
        payment_data = event_json["object"]
        order_id = payment_data["metadata"]["order_id"]

        # Обновляем статус заказа
        order = Order.objects.get(id=order_id)
        logger.info(
            f"Обработка события {event} для заказа {order_id}, текущий статус is_paid: {order.is_paid}"
        )
        if event == "payment.succeeded" and not order.is_paid:
            order.is_paid = True
            order.payment_status = "succeeded"
            order.save()
            logger.info(
                f"Order {order_id} marked as paid (payment {payment_data['id']})"
            )

            # Проверяем параметр reserve_order для оплаты забронированных билетов
            if request.GET.get("reserve_order"):
                logger.info(f"Оплата забронированного билета для заказа {order_id}")

            # Проверяем параметр reserve_order в POST данных
            if request.POST.get("reserve_order"):
                reserve_order_id = request.POST.get("reserve_order")
                logger.info(
                    f"Обработка оплаты для забронированного заказа {reserve_order_id}"
                )

            # Отправляем уведомление о покупке билетов
            logger.info(
                f"Начало отправки уведомления о покупке билетов для заказа {order_id}"
            )
            try:
                # Получаем email пользователя из данных заказа
                email = order.participant_data.get("email")
                if not email:
                    logger.warning(
                        f"Не удалось отправить уведомление: отсутствует email в данных заказа {order.id}"
                    )
                    return

                # Получаем пользователя по email (если существует)
                try:
                    user = CustomUser.objects.get(email=email)
                    # Отправляем уведомление
                    send_multiple_tickets_notification(user, [order])
                    logger.info(
                        f"Уведомление о покупке билетов успешно отправлено пользователю {user.email}"
                    )
                except CustomUser.DoesNotExist:
                    # Если пользователь не зарегистрирован, отправляем уведомление на email
                    send_ticket_notification_to_email(order)

            except Exception as e:
                logger.exception(
                    f"Ошибка отправки уведомления о покупке билетов: {str(e)}"
                )
    except Order.DoesNotExist:
        logger.error(f"Order {order_id} not found")

    # Всегда возвращаем HTTP 200 (ЮKassa ждет этого ответа)
    return HttpResponse(status=200)


def send_multiple_tickets_notification(user, orders, request=None):
    subject = "Ваши электронные билеты"
    activation_link = None
    if request:
        activation_link = request.build_absolute_uri(
            reverse("activate_account", args=[user.pk])
        )

    # Формируем ссылку на личный кабинет
    dashboard_url = "#"
    if request and user.user_type != "guest":
        dashboard_url = request.build_absolute_uri(reverse("visitor:dashboard"))

    # Определяем текст и ссылку для кнопки в зависимости от типа пользователя
    if user.user_type == "guest":
        button_text = "Создайте пароль, чтобы просматривать ваши заказы"
        button_url = activation_link or "#"
        button_color = "#3498db"
    else:
        button_text = "Перейти в личный кабинет для просмотра билетов"
        button_url = dashboard_url
        button_color = "#9b59b6"

    # Определяем ссылку на поддержку
    support_url = "#"
    if hasattr(user, "is_authenticated") and user.is_authenticated:
        support_url = (
            request.build_absolute_uri(reverse("support_dashboard")) if request else "#"
        )
    else:
        if request:
            register_url = request.build_absolute_uri(reverse("register"))
            support_url = f"{register_url}?email={user.email}&next={request.build_absolute_uri(reverse('support_dashboard'))}"

    # Формируем информацию о всех билетах
    tickets_info = ""
    total_amount = 0
    for order in orders:
        # Для каждого билета в заказе генерируем отдельный QR-код
        for i in range(1, order.quantity + 1):
            # Генерация QR-кода для каждого билета
            try:

                qr = qrcode.QRCode(
                    version=1,
                    error_correction=qrcode.constants.ERROR_CORRECT_L,
                    box_size=10,
                    border=4,
                )
                qr.add_data(f"Order ID: {order.id}, Ticket: {i}")
                qr.make(fit=True)
                img = qr.make_image(fill_color="black", back_color="white")

                # Конвертируем QR-код в base64 для вставки в HTML
                buffered = io.BytesIO()
                img.save(buffered, format="PNG")
                img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")

                tickets_info += f"""
                <div style="background-color: #f8f9fa; padding: 15px; border-radius: 5px; margin: 20px 0;">
                    <p><strong>Тип билета:</strong> {order.ticket.name}</p>
                    <p><strong>Билет №{i} из {order.quantity}</strong></p>
                    <p><strong>Сумма:</strong> {order.total_price} ₽</p>
                    <p><strong>Дата и время:</strong> {order.ticket.event.date_time.strftime('%d.%m.%Y %H:%M')}</p>
                    <p><strong>Место проведения:</strong> {order.ticket.event.place_data.get('address', 'Не указано') if isinstance(order.ticket.event.place_data, dict) else getattr(order.ticket.event.place_data, 'address', 'Не указано')}</p>
                    <p><strong>QR-код для билета №{i}:</strong></p>
                    <img src="data:image/png;base64,{img_str}" alt="QR-код для билета #{i} заказа #{order.id}" style="width: 100px; height: 100px; display: block; margin: 0 auto;">
                </div>
                """
            except Exception as e:
                logger.exception(
                    f"Ошибка генерации QR-кода для билета {i} заказа {order.id}: {str(e)}"
                )
                tickets_info += f"""
                <div style="background-color: #f8f9fa; padding: 15px; border-radius: 5px; margin: 20px 0;">
                    <p><strong>Тип билета:</strong> {order.ticket.name}</p>
                    <p><strong>Билет №{i} из {order.quantity}</strong></p>
                    <p><strong>Сумма:</strong> {order.total_price} ₽</p>
                    <p><strong>Дата и время:</strong> {order.ticket.event.date_time.strftime('%d.%m.%Y %H:%M')}</p>
                    <p><strong>Место проведения:</strong> {order.ticket.event.place_data.get('address', 'Не указано') if isinstance(order.ticket.event.place_data, dict) else getattr(order.ticket.event.place_data, 'address', 'Не указано')}</p>
                    <p><strong>QR-код для билета №{i}:</strong> Ошибка генерации QR-кода</p>
                </div>
                """
        total_amount += order.total_price

    message = f"""
    <html>
    <body>
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <h2 style="color: #2c3e50;">Здравствуйте, {user.get_full_name() or user.email}!</h2>

            <p>Благодарим вас за покупку билетов на мероприятие:</p>
            <h3 style="color: #3498db;">{orders[0].ticket.event.title}</h3>

            {tickets_info}

            <div style="background-color: #f8f9fa; padding: 15px; border-radius: 5px; margin: 20px 0;">
            <p><strong>Итого к оплате:</strong> {total_amount} руб.</p>
            </div>

            <div style="text-align: center; margin: 30px 0;">
                <a href="{button_url}" style="
                    display: inline-block;
                    padding: 12px 24px;
                    background-color: {button_color};
                    color: white;
                    text-decoration: none;
                    border-radius: 4px;
                    font-weight: bold;
                ">{button_text}</a>
            </div>

            <div style="
                margin-top: 40px;
                padding-top: 20px;
                border-top: 1px solid #eee;
                font-size: 12px;
                color: #7f8c8d;
            ">
                <p>Если у вас возникли вопросы, обратитесь в нашу <a href="{support_url}">службу поддержки</a>.</p>
                <p>
                    <a href="#" style="color: #7f8c8d; text-decoration: none; margin: 0 10px;">Политика конфиденциальности</a> |
                    <a href="#" style="color: #7f8c8d; text-decoration: none; margin: 0 10px;">Поддержка</a>
                </p>
            </div>
        </div>
    </body>
    </html>
    """
    send_mail(
        subject, "", "dim.anosoff2018@yandex.ru", [user.email], html_message=message
    )


def send_reservation_notification(order):
    """Отправляет уведомление о бронировании билета."""
    from django.contrib.sites.shortcuts import get_current_site

    user_email = order.participant_data.get("email")
    if not user_email:
        return

    event = order.ticket.event
    payment_link = generate_payment_link(order)

    subject = f"Ваш билет на мероприятие {event.title} забронирован"

    context = {
        "order": order,
        "event": event,
        "payment_link": payment_link,
        "site_name": get_current_site(None).name,
    }

    html_message = render_to_string("emails/reservation_notification.html", context)
    plain_message = strip_tags(html_message)

    send_mail(
        subject,
        plain_message,
        "noreply@eventplatform.com",
        [user_email],
        html_message=html_message,
    )


def send_ticket_notification_to_email(order):
    """Отправляет уведомление о покупке билета на email."""
    from django.contrib.sites.shortcuts import get_current_site

    user_email = order.participant_data.get("email")
    if not user_email:
        return

    event = order.ticket.event
    payment_link = generate_payment_link(order)

    subject = f"Ваш билет на мероприятие {event.title}"

    context = {
        "order": order,
        "event": event,
        "payment_link": payment_link,
        "site_name": get_current_site(None).name,
    }

    html_message = render_to_string("emails/ticket_notification.html", context)
    plain_message = strip_tags(html_message)

    send_mail(
        subject,
        plain_message,
        "noreply@eventplatform.com",
        [user_email],
        html_message=html_message,
    )
    logger.info(
        f"Уведомление о покупке билетов успешно отправлено на email {user_email}"
    )


def _get_ticket_quantities_and_validate(request, event):
    """Собирает и валидирует выбранные билеты."""
    tickets = event.tickets.all()
    ticket_quantities = {}
    error_message = None

    for ticket in tickets:
        quantity_key = f"quantity_{ticket.id}"
        quantity = int(request.POST.get(quantity_key, 0) or 0)
        if quantity > 0:
            if not ticket.is_available(quantity):
                error_message = f"Недостаточно билетов типа '{ticket.name}'. Доступно: {ticket.get_available_count()}"
                break
            ticket_quantities[ticket] = quantity

    if not ticket_quantities:
        error_message = "Пожалуйста, выберите хотя бы один билет"

    return ticket_quantities, error_message


def _create_or_update_user(request):
    """Создаёт или обновляет пользователя по email."""
    email = (request.POST.get("email") or "").strip()
    first_name = (request.POST.get("first_name") or "").strip()
    last_name = (request.POST.get("last_name") or "").strip()
    phone = (request.POST.get("phone") or "").strip()

    user, created = CustomUser.objects.get_or_create(
        email=email,
        defaults={
            "first_name": first_name,
            "last_name": last_name,
            "phone": phone,
            "user_type": "guest",
            "username": email,
        },
    )
    if not created:
        user.first_name = first_name
        user.last_name = last_name
        user.phone = phone
        user.save()
    if created:
        user.set_unusable_password()
        user.save()
    return user


def _create_orders(user, event, ticket_quantities, request):
    """Создаёт заказы в транзакции."""
    try:
        with transaction.atomic():
            orders = []
            for ticket, quantity in ticket_quantities.items():
                ticket = Ticket.objects.select_for_update().get(pk=ticket.pk)
                if not ticket.is_available(quantity):
                    raise ValueError(
                        f"Недостаточно билетов типа '{ticket.name}'. Доступно: {ticket.get_available_count()}"
                    )
                total_price = ticket.price * quantity
                platform_commission = total_price * (event.commission_rate / 100)

                purchase_type = request.POST.get("purchase_type", "paid_ticket")
                is_booking = (
                    event.allow_booking_without_payment
                    and request.POST.get("book_without_payment") == "on"
                )

                if purchase_type == "free_registration":
                    total_price = 0
                    platform_commission = 0
                    is_paid = True
                    payment_status = "succeeded"
                    payment_deadline = None
                elif is_booking:
                    is_paid = False
                    payment_status = "reserved"
                    payment_deadline = event.date_time - timezone.timedelta(hours=24)
                else:
                    is_paid = False
                    payment_status = "pending"
                    payment_deadline = None

                order = Order.objects.create(
                    ticket=ticket,
                    participant_data={
                        "email": user.email,
                        "first_name": user.first_name,
                        "last_name": user.last_name,
                        "phone": request.POST.get("phone", ""),
                    },
                    total_price=total_price,
                    quantity=quantity,
                    is_paid=is_paid,
                    payment_status=payment_status,
                    platform_commission=platform_commission,
                    purchase_type=purchase_type,
                    payment_deadline=payment_deadline,
                    utm_source=request.POST.get("utm_source")
                    or request.GET.get("utm_source"),
                    utm_medium=request.POST.get("utm_medium")
                    or request.GET.get("utm_medium"),
                    utm_campaign=request.POST.get("utm_campaign")
                    or request.GET.get("utm_campaign"),
                    utm_term=request.POST.get("utm_term")
                    or request.GET.get("utm_term"),
                    utm_content=request.POST.get("utm_content")
                    or request.GET.get("utm_content"),
                )
                orders.append(order)
            return orders
    except IntegrityError as e:
        logger.error(f"Ошибка целостности данных при покупке билетов: {e}")
        return None


def _process_payment_and_notifications(orders, request, event, user):
    """Обрабатывает оплату, отправляет уведомления, возвращает результат для AJAX или редирект."""
    is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest"
    require_payment = not (
        event.allow_booking_without_payment
        and request.POST.get("book_without_payment") == "on"
    )

    # Отправка уведомлений
    try:
        send_multiple_tickets_notification(user, orders, request)
    except Exception as e:
        logger.exception(f"Ошибка отправки письма: {str(e)}")

    # Проверка, все ли билеты выкуплены
    all_tickets_sold = all(
        ticket.get_available_count() == 0 for ticket in event.tickets.all()
    )
    if all_tickets_sold and not event.has_sold_tickets:
        event.has_sold_tickets = True
        event.save()
        try:
            send_partner_all_tickets_sold_notification(event)
        except Exception as e:
            logger.exception(f"Ошибка отправки уведомления партнёру: {str(e)}")

    # Обработка оплаты через ЮKassa (только если требуется оплата)
    if require_payment:
        try:
            total_amount = sum(order.total_price for order in orders)
            primary_order_id = orders[0].id

            payment_data = {
                "amount": {"value": str(total_amount), "currency": "RUB"},
                "confirmation": {"type": "embedded"},
                "capture": True,
                "metadata": {"order_id": str(primary_order_id)},
                "description": f"Оплата билетов на мероприятие {event.title}",
            }

            auth_string = f"{settings.YOOKASSA_SHOP_ID}:{settings.YOOKASSA_SECRET_KEY}"
            auth_base64 = base64.b64encode(auth_string.encode("ascii")).decode("ascii")

            headers = {
                "Idempotence-Key": str(uuid.uuid4()),
                "Content-Type": "application/json",
                "Authorization": f"Basic {auth_base64}",
            }
            response = requests.post(
                "https://api.yookassa.ru/v3/payments",
                headers=headers,
                json=payment_data,
            )

            if response.ok:
                payment_response = response.json()
                confirmation_token = payment_response["confirmation"][
                    "confirmation_token"
                ]

                if is_ajax:
                    return_url = (
                        request.build_absolute_uri(reverse("landing_page"))
                        + "?success=payment_completed"
                    )
                    return {
                        "success": True,
                        "confirmation_token": confirmation_token,
                        "return_url": return_url,
                    }
                else:
                    return redirect(
                        reverse("landing_page") + "?success=payment_completed"
                    )
            else:
                logger.error(f"Ошибка создания платежа в ЮKassa: {response.text}")
                messages.error(
                    request, "Ошибка при создании платежа. Попробуйте еще раз."
                )
        except Exception as e:
            logger.error(f"Ошибка при работе с ЮKassa: {str(e)}")
            messages.error(request, "Ошибка при обработке платежа. Попробуйте еще раз.")

    # Если оплата не требуется (бронирование или бесплатная регистрация)
    if is_ajax:
        if (
            event.allow_booking_without_payment
            and request.POST.get("book_without_payment") == "on"
        ):
            payment_deadline_str = orders[0].payment_deadline.strftime("%d.%m.%Y %H:%M")
            return {
                "success": True,
                "message": f"Бронирование успешно завершено! Ваши билеты забронированы до {payment_deadline_str}. "
                f"Оплатите их до этого времени, иначе бронь будет автоматически отменена. "
                f"Информация отправлена на ваш email.",
            }
        else:
            return {
                "success": True,
                "message": "Регистрация успешно завершена. Билеты отправлены на ваш email.",
            }
    else:
        return redirect(reverse("landing_page") + "?success=ticket_purchased")


@login_required
@require_http_methods(["GET", "POST"])
def buy_ticket(request, event_id):
    """Представление для покупки билетов на мероприятие."""
    event = get_object_or_404(Event, id=event_id)

    if request.method == "GET":
        tickets = event.tickets.all()
        has_paid_tickets = any(ticket.price > 0 for ticket in tickets)
        return render(
            request,
            "buy_ticket.html",
            {
                "event": event,
                "tickets": tickets,
                "allow_booking_without_payment": event.allow_booking_without_payment,
            },
        )

    # POST-запрос
    user = _create_or_update_user(request)
    ticket_quantities, error_message = _get_ticket_quantities_and_validate(
        request, event
    )

    if error_message:
        messages.error(request, error_message)
        return render(
            request,
            "buy_ticket.html",
            {
                "event": event,
                "tickets": event.tickets.all(),
                "allow_booking_without_payment": event.allow_booking_without_payment,
            },
        )

    orders = _create_orders(user, event, ticket_quantities, request)
    if not orders:
        messages.error(
            request, "Произошла ошибка при покупке билетов. Попробуйте еще раз."
        )
        return render(
            request,
            "buy_ticket.html",
            {
                "event": event,
                "tickets": event.tickets.all(),
                "allow_booking_without_payment": event.allow_booking_without_payment,
            },
        )

    # Обработка оплаты и уведомлений
    result = _process_payment_and_notifications(orders, request, event, user)

    # Если это AJAX — возвращаем JSON, иначе — редирект
    if isinstance(result, dict):
        return JsonResponse(result)
    else:
        return result
