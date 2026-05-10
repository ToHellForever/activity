from django.shortcuts import (
    render,
    redirect,
    get_object_or_404,
    HttpResponseRedirect,
    reverse,
)
from django.http import JsonResponse, HttpResponseBadRequest, HttpResponse
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth import logout as auth_logout
from .forms import CustomAuthenticationForm, CustomUserCreationForm
from django.views.decorators.cache import never_cache
from django.contrib.auth import login, authenticate
from .forms import CustomAuthenticationForm
from .models import Event, Ticket
from django.contrib.auth.decorators import login_required, user_passes_test
from core.forms import SupportTicketForm
from django.utils import timezone
from .models import SupportTicket, SupportMessage, SupportAttachment, CustomUser, Order
from django import forms
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth import update_session_auth_hash
from django.views.decorators.http import require_POST
from django.core.mail import send_mail
from django.contrib.auth.hashers import make_password
from django.views.decorators.http import require_http_methods
from django.contrib import messages
from django.conf import settings
from django.db import transaction, IntegrityError
import uuid
import logging
import random
import string
import requests
import json
import base64
from django.views.decorators.csrf import csrf_exempt

logger = logging.getLogger(__name__)


@csrf_exempt
def yookassa_webhook(request):
    # Логируем все входящие данные (для отладки)
    logger.info(f"Webhook received. Method: {request.method}")
    logger.info(f"Headers: {request.headers}")
    logger.info(f"Body: {request.body}")

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
        if event == "payment.succeeded" and not order.is_paid:
            order.is_paid = True
            order.payment_status = "succeeded"
            order.save()
            logger.info(
                f"Order {order_id} marked as paid (payment {payment_data['id']})"
            )
        elif event == "payment.canceled":
            order.payment_status = "canceled"
            order.save()
            logger.info(
                f"Order {order_id} marked as canceled (payment {payment_data['id']})"
            )

    except Order.DoesNotExist:
        logger.error(f"Order {order_id} not found")
    except Exception as e:
        logger.error(f"Error processing webhook: {str(e)}")

    # Всегда возвращаем HTTP 200 (ЮKassa ждет этого ответа)
    return HttpResponse(status=200)


def landing_page(request):
    return render(request, "landing.html")


@login_required
def change_password(request):
    """Отдельная страница для смены пароля."""
    if request.method == "POST":
        password_form = PasswordChangeForm(user=request.user, data=request.POST)
        if password_form.is_valid():
            password_form.save()
            update_session_auth_hash(request, password_form.user)
            return redirect("partner:profile_edit")
    else:
        password_form = PasswordChangeForm(user=request.user)
    return render(request, "change_password.html", {"password_form": password_form})


@never_cache
def login_view(request):
    if request.user.is_authenticated:
        # Если пользователь уже вошел, сразу редиректим его в нужный кабинет
        if request.user.user_type == "partner":
            return redirect("partner:dashboard")
        else:
            return redirect("visitor:dashboard")

    if request.method == "POST":
        form = CustomAuthenticationForm(request.POST, request=request)
        if form.is_valid():
            user = form.cleaned_data["user"]
            login(request, user)
            if user.user_type == "partner":
                return redirect("partner:dashboard")
            else:
                return redirect("visitor:dashboard")
    else:
        form = CustomAuthenticationForm()

    return render(request, "registration/login.html", {"form": form})


def generate_temporary_password(length=10):
    """Генерация временного пароля."""
    characters = string.ascii_letters + string.digits
    return "".join(random.choice(characters) for _ in range(length))


@never_cache
def forgot_password(request):
    """Обработка запроса на восстановление пароля."""
    if request.method == "POST":
        email = request.POST.get("email")
        try:
            user = CustomUser.objects.get(email=email)
            # Генерируем временный пароль
            temp_password = generate_temporary_password()
            # Устанавливаем временный пароль
            user.set_password(temp_password)
            user.save()
            # Формируем ссылку на страницу входа
            login_url = request.build_absolute_uri(reverse("login"))

            # Отправляем письмо с временным паролем и ссылкой на вход
            subject = "Восстановление пароля"
            message = f"""
                Здравствуйте!
                
                Ваш временный пароль: {temp_password}.
                
                Вы можете войти, используя этот пароль, по следующей ссылке: {login_url}
                
                Пожалуйста, измените пароль после входа в систему.
            """
            send_mail(
                subject,
                message,
                "dim.anosoff2018@yandex.ru",
                [user.email],
                fail_silently=False,
            )
            return render(
                request, "registration/forgot_password_success.html", {"email": email}
            )
        except CustomUser.DoesNotExist:
            # Не показываем, существует ли пользователь с таким email
            return render(
                request, "registration/forgot_password_success.html", {"email": email}
            )
    return render(request, "registration/forgot_password.html")


@never_cache
def register_view(request):
    """Обрабатывает регистрацию нового пользователя."""
    if request.method == "POST":
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()  # Сохраняем пользователя в БД
            # Указываем бэкенд для пользователя (нужно при нескольких бэкендах)
            user.backend = "core.backends.EmailBackend"
            # Сразу логиним пользователя после регистрации
            login(request, user)

            # Редирект в зависимости от выбранной роли при регистрации
            if user.user_type == "partner":
                return redirect("partner:dashboard")
            else:
                return redirect("visitor:dashboard")
    else:
        form = CustomUserCreationForm()

    return render(request, "registration/register.html", {"form": form})


def custom_logout(request):
    """
    Кастомная функция для выхода из системы.
    Гарантирует редирект на страницу входа.
    """
    # Выполняем стандартное действие выхода
    auth_logout(request)

    # Редиректим на страницу входа по имени URL
    return redirect("login")


@login_required
def support_dashboard(request):
    """
    Главная страница поддержки. Слева список тикетов, справа чат.
    """
    # --- НОВАЯ ЛОГИКА: Создание тикета на этой же странице ---
    if request.method == "POST":
        # Проверяем, пришли ли данные для создания НОВОГО тикета
        new_subject = request.POST.get("new_subject")
        new_message = request.POST.get("new_message")
        files = request.FILES.getlist("attachment")
        event_id = request.POST.get("event_id")

        if new_subject and new_message:
            # Создаем новый тикет
            ticket = SupportTicket.objects.create(
                subject=new_subject,
                user=request.user,
                status="new",
                event_id=event_id if event_id else None,
            )
            # Создаем первое сообщение в чате
            message = SupportMessage.objects.create(
                ticket=ticket, user=request.user, is_from_user=True, text=new_message
            )

            # Сохраняем вложения, если они есть
            for file in files:
                SupportAttachment.objects.create(message=message, file=file)

            # Перенаправляем на эту же страницу, но с выбранным новым тикетом
            return redirect(f"/support/?ticket_id={ticket.id}")

    # --- СТАРАЯ ЛОГИКА: Отображение страницы ---
    tickets = SupportTicket.objects.filter(user=request.user).order_by("-created_at")
    selected_ticket = None
    chat_messages = []

    if request.GET.get("ticket_id"):
        ticket_id = request.GET.get("ticket_id")
        selected_ticket = get_object_or_404(
            SupportTicket, id=ticket_id, user=request.user
        )
        chat_messages = selected_ticket.messages.all()

    # Получаем мероприятия пользователя с проданными билетами для формы создания тикета
    user_events = Event.objects.filter(organizer=request.user, has_sold_tickets=True)

    context = {
        "tickets": tickets,
        "selected_ticket": selected_ticket,
        "chat_messages": chat_messages,
        "events": user_events,
    }
    return render(request, "support_dashboard.html", context)


@require_POST
@login_required
def send_support_message(request):
    """Обрабатывает отправку нового сообщения в рамках существующего тикета поддержки."""
    ticket_id = request.POST.get("ticket_id")
    text = request.POST.get("text")
    files = request.FILES.getlist("attachment")  # Получаем список файлов

    if ticket_id and (text or files):
        ticket = get_object_or_404(SupportTicket, id=ticket_id)

        # Создаем новое сообщение
        message = SupportMessage.objects.create(
            ticket=ticket,
            user=request.user,
            is_from_user=(not request.user.is_staff),  # Если staff — это модератор
            text=text,
        )

        # Сохраняем вложения, если они есть
        for file in files:
            SupportAttachment.objects.create(message=message, file=file)

        # Логика редиректа
        if request.user.is_staff:  # Если модератор — не редиректим
            return HttpResponseRedirect(request.META.get("HTTP_REFERER", "/"))
        else:  # Если пользователь — редиректим на страницу тикета
            return redirect(f"/support/?ticket_id={ticket_id}")

    messages.error(request, "Ошибка отправки сообщения.")
    return redirect("support_dashboard")


def upload_image(request):
    if request.method == "POST":
        data_url = request.POST.get("data")
        format, imgstr = data_url.split(";base64,")
        ext = format.split("/")[1]
        data = ContentFile(base64.b64decode(imgstr), name=f"image.{ext}")

        # Создаем вложение и возвращаем его ID
        attachment = Attachment.objects.create(file=data)
        return JsonResponse({"attachment_id": attachment.id})

    return HttpResponseBadRequest("Некорректный запрос")


def is_moderator(user):
    return user.is_superuser or user.groups.filter(name="Модераторы").exists()


@user_passes_test(is_moderator, login_url="/login/")
@login_required
def moderator_dashboard(request):
    """
    Главная страница модератора. Слева список тикетов, справа чат.
    """
    # Определяем фильтр по статусу (новые, в работе, закрытые)
    filter_status = request.GET.get("status", "new")

    # Получаем тикеты по фильтру
    tickets = SupportTicket.objects.filter(status=filter_status).order_by("-created_at")

    # По умолчанию чат пустой
    selected_ticket = None
    chat_messages = []

    # Если выбран конкретный тикет для просмотра
    if request.GET.get("ticket_id"):
        ticket_id = request.GET.get("ticket_id")
        selected_ticket = get_object_or_404(SupportTicket, id=ticket_id)
        chat_messages = selected_ticket.messages.all()

    context = {
        "tickets": tickets,
        "selected_ticket": selected_ticket,
        "chat_messages": chat_messages,
        "filter_status": filter_status,  # Передаем статус для фильтров
    }
    return render(request, "moderator_dashboard.html", context)


def update_ticket_status(request, ticket_id):
    ticket = get_object_or_404(SupportTicket, id=ticket_id)
    new_status = request.POST.get("status")
    ticket.status = new_status
    ticket.save()
    return redirect(reverse("moderator_dashboard") + "?ticket_id=" + str(ticket_id))


def event_list(request):
    active_events = Event.objects.filter(status="active").order_by("date_time")

    # Получаем все теги для фильтра
    all_tags = Event.tags.most_common()

    # Получаем выбранные теги из GET-запроса
    selected_tags = request.GET.getlist("tags")

    # Фильтруем мероприятия по выбранным тегам, если они есть
    if selected_tags:
        active_events = active_events.filter(tags__name__in=selected_tags).distinct()

    return render(
        request,
        "events/event_list.html",
        {"events": active_events, "all_tags": all_tags, "selected_tags": selected_tags},
    )


def event_detail(request, event_id):
    event = get_object_or_404(Event, id=event_id)
    return render(request, "events/event_detail.html", {"event": event})


@require_http_methods(["GET", "POST"])
def buy_ticket(request, event_id):
    event = get_object_or_404(Event, id=event_id)

    if request.method == "GET":
        # Показываем форму покупки
        tickets = event.tickets.all()
        return render(
            request,
            "buy_ticket.html",
            {
                "event": event,
                "tickets": tickets,
                "allow_booking_without_payment": event.allow_booking_without_payment,
            },
        )

    # Обработка POST-запроса
    email = (request.POST.get("email") or "").strip()
    first_name = (request.POST.get("first_name") or "").strip()
    last_name = (request.POST.get("last_name") or "").strip()
    phone = (request.POST.get("phone") or "").strip()

    # Создаём или получаем пользователя по email
    user, created = CustomUser.objects.get_or_create(
        email=email,
        defaults={
            "first_name": first_name,
            "last_name": last_name,
            "user_type": "guest",
            "username": email,  # Используем email как username
        },
    )

    # Обновляем данные пользователя, если он уже существовал
    if not created:
        user.first_name = first_name
        user.last_name = last_name
        user.save()

    if created:
        # Гость без пароля
        user.set_unusable_password()
        user.save()

    # Получаем все билеты события для проверки
    tickets = event.tickets.all()
    ticket_quantities = {}
    total_price = 0
    error_message = None

    # Собираем информацию о выбранных билетах
    for ticket in tickets:
        quantity_key = f"quantity_{ticket.id}"
        quantity = int(request.POST.get(quantity_key, 0) or 0)

        if quantity > 0:
            # Проверяем доступность
            if not ticket.is_available(quantity):
                error_message = f"Недостаточно билетов типа '{ticket.name}'. Доступно: {ticket.get_available_count()}"
                break

            ticket_quantities[ticket] = quantity
            total_price += ticket.price * quantity

    # Если есть ошибка или не выбрано ни одного билета
    if error_message:
        messages.error(request, error_message)
        return render(
            request,
            "buy_ticket.html",
            {
                "event": event,
                "tickets": tickets,
                "allow_booking_without_payment": event.allow_booking_without_payment,
            },
        )

    if not ticket_quantities:
        messages.error(request, "Пожалуйста, выберите хотя бы один билет")
        return render(
            request,
            "buy_ticket.html",
            {
                "event": event,
                "tickets": tickets,
                "allow_booking_without_payment": event.allow_booking_without_payment,
            },
        )

    # Проверяем, нужно ли оплачивать сразу или можно забронировать
    is_booking_without_payment = (
        event.allow_booking_without_payment
        and request.POST.get("book_without_payment") == "on"
    )

    # Если требуется оплата (не бронирование), будем использовать ЮKassa
    require_payment = not is_booking_without_payment

    # Если требуется оплата (не бронирование), будем использовать ЮKassa
    require_payment = not is_booking_without_payment

    # Добавляем отладочный вывод для проверки логики
    logger.info(
        f"Проверка логики оплаты: require_payment={require_payment}, is_booking_without_payment={is_booking_without_payment}"
    )

    # Отладочный вывод UTM-меток
    print("UTM Source from POST:", request.POST.get("utm_source"))
    print("UTM Source from GET:", request.GET.get("utm_source"))
    print("UTM Medium from POST:", request.POST.get("utm_medium"))
    print("UTM Medium from GET:", request.GET.get("utm_medium"))
    print("UTM Campaign from POST:", request.POST.get("utm_campaign"))
    print("UTM Campaign from GET:", request.GET.get("utm_campaign"))

    # Создаем заказы для каждого типа билетов
    orders = []
    try:
        with transaction.atomic():
            for ticket, quantity in ticket_quantities.items():
                logger.debug(
                    f"Начало обработки билета {ticket.id}, доступно до блокировки: {ticket.get_available_count()}"
                )

                # Блокируем билет для предотвращения гонки
                ticket = Ticket.objects.select_for_update().get(pk=ticket.pk)
                logger.debug(
                    f"Билет {ticket.id} заблокирован, доступно после блокировки: {ticket.get_available_count()}"
                )

                # Повторно проверяем доступность после блокировки
                if not ticket.is_available(quantity):
                    logger.warning(
                        f"Недостаточно билетов типа '{ticket.name}'. Запрошено: {quantity}, доступно: {ticket.get_available_count()}"
                    )
                    raise ValueError(
                        f"Недостаточно билетов типа '{ticket.name}'. Доступно: {ticket.get_available_count()}"
                    )

                logger.debug(
                    f"Создание заказа для билета {ticket.id}, количество: {quantity}"
                )
                order = Order.objects.create(
                    ticket=ticket,
                    participant_data={
                        "email": email,
                        "first_name": first_name,
                        "last_name": last_name,
                        "phone": phone,
                    },
                    total_price=ticket.price * quantity,
                    quantity=quantity,
                    is_paid=not is_booking_without_payment,  # Если бронирование без оплаты, ставим is_paid=False
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
                logger.debug(
                    f"Заказ для билета {ticket.id} успешно создан, ID заказа: {order.id}"
                )
    except IntegrityError as e:
        messages.error(
            request, "Произошла ошибка при покупке билетов. Попробуйте еще раз."
        )
        logger.error(f"Ошибка целостности данных при покупке билетов: {e}")
        logger.error(
            f"Текущее доступное количество билетов: {ticket.get_available_count()}"
        )
        return render(
            request,
            "buy_ticket.html",
            {
                "event": event,
                "tickets": tickets,
                "allow_booking_without_payment": event.allow_booking_without_payment,
            },
        )
    except ValueError as e:
        messages.error(request, str(e))
        return render(
            request,
            "buy_ticket.html",
            {
                "event": event,
                "tickets": tickets,
                "allow_booking_without_payment": event.allow_booking_without_payment,
            },
        )

    # Устанавливаем флаг has_sold_tickets для события, если билеты проданы
    if not event.has_sold_tickets:
        event.has_sold_tickets = True
        event.save()

        # Устанавливаем дедлайн оплаты для бронирований без оплаты
        if is_booking_without_payment:
            # Дедлайн - за 24 часа до начала мероприятия
            payment_deadline = event.date_time - timezone.timedelta(hours=24)
            order.payment_deadline = payment_deadline
            order.save()

        orders.append(order)

    # Отправляем одно уведомление с информацией о всех билетах
    try:
        send_multiple_tickets_notification(user, orders, request)
    except Exception as e:
        logger.exception("Ошибка отправки письма: %s", e)

    # Проверяем, все ли билеты на мероприятие выкуплены
    all_tickets_sold = True
    for ticket in event.tickets.all():
        if ticket.get_available_count() > 0:
            all_tickets_sold = False
            break

    # Логируем результат проверки
    logger.debug(
        f"Проверка на выкуп всех билетов для мероприятия {event.id}: {all_tickets_sold}"
    )

    # Если все билеты выкуплены, отправляем уведомление партнёру
    if all_tickets_sold:
        try:
            logger.debug(f"Отправка уведомления партнёру для мероприятия {event.id}")
            send_partner_all_tickets_sold_notification(event)
            logger.debug(f"Уведомление партнёру для мероприятия {event.id} отправлено")
        except Exception as e:
            logger.exception("Ошибка отправки уведомления партнёру: %s", e)

    # Если требуется оплата через ЮKassa, генерируем платежный токен
    if require_payment:
        yookassa_payment_token = None
        try:
            # Создаем платеж в ЮKassa для получения токена
            total_amount = sum(
                ticket.price * quantity
                for ticket, quantity in ticket_quantities.items()
            )

            # Подготавливаем данные для создания платежа
            # Используем только первый заказ для упрощения (или можно сделать join через запятую)
            primary_order_id = orders[0].id
            payment_data = {
                "amount": {"value": str(total_amount), "currency": "RUB"},
                "confirmation": {"type": "embedded"},
                "capture": True,
                "metadata": {"order_id": str(primary_order_id)},
                "description": f"Оплата билетов на мероприятие {event.title}",
            }

            # Логируем данные для отладки
            logger.info(f"Создание платежа в ЮKassa: {payment_data}")

            # Формируем заголовок Authorization в формате Basic <base64(shopId:secretKey)>
            auth_string = f"{settings.YOOKASSA_SHOP_ID}:{settings.YOOKASSA_SECRET_KEY}"
            auth_bytes = auth_string.encode('ascii')
            auth_base64 = base64.b64encode(auth_bytes).decode('ascii')
            
            # Логируем заголовок для отладки
            logger.info(f"Сформированный заголовок Authorization: Basic ***{auth_base64[-10:]}")
            
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

            # Добавляем отладочный вывод статуса ответа от ЮKassa
            logger.info(f"Ответ от ЮKassa: {response.status_code}, {response.text}")

            if response.ok:
                payment_response = response.json()
                yookassa_payment_token = payment_response["confirmation"][
                    "confirmation_token"
                ]
                logger.info(
                    f"Успешно создан платеж в ЮKassa. Токен: {yookassa_payment_token}"
                )
            else:
                logger.error(f"Ошибка создания платежа в ЮKassa: {response.text}")
                messages.error(
                    request, "Ошибка при создании платежа. Попробуйте еще раз."
                )
                return render(
                    request,
                    "buy_ticket.html",
                    {
                        "event": event,
                        "tickets": tickets,
                        "allow_booking_without_payment": event.allow_booking_without_payment,
                    },
                )
        except Exception as e:
            logger.error(f"Ошибка при работе с ЮKassa: {str(e)}")
            messages.error(request, "Ошибка при обработке платежа. Попробуйте еще раз.")
            return render(
                request,
                "buy_ticket.html",
                {
                    "event": event,
                    "tickets": tickets,
                    "allow_booking_without_payment": event.allow_booking_without_payment,
                },
            )

    from django.urls import reverse

    # Перенаправляем на страницу оплаты или успешной покупки
    if require_payment and yookassa_payment_token:
        # Логируем передачу токена в шаблон
        logger.info(f"Передача токена в шаблон: {yookassa_payment_token}")
        # Формируем абсолютный URL для возврата после оплаты
        return_url = request.build_absolute_uri(reverse("landing_page")) + "?success=payment_completed"
        # Передаем токен и URL в шаблон для инициализации виджета
        return render(
            request,
            "buy_ticket.html",
            {
                "event": event,
                "tickets": tickets,
                "allow_booking_without_payment": event.allow_booking_without_payment,
                "yookassa_payment_token": yookassa_payment_token,
                "yookassa_return_url": return_url,
                "orders": orders,
            },
        )
    else:
        url = reverse("landing_page") + "?success=ticket_purchased"
        return redirect(url)


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
        # Генерация QR-кода
        import qrcode
        import io
        import base64

        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(f"Order ID: {order.id}")
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")

        # Конвертируем QR-код в base64 для вставки в HTML
        buffered = io.BytesIO()
        img.save(buffered, format="PNG")
        img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")

        tickets_info += f"""
        <div style="background-color: #f8f9fa; padding: 15px; border-radius: 5px; margin: 20px 0;">
            <p><strong>Тип билета:</strong> {order.ticket.name}</p>
            <p><strong>Количество:</strong> {order.quantity}</p>
            <p><strong>Сумма:</strong> {order.total_price} ₽</p>
            <p><strong>Дата и время:</strong> {order.ticket.event.date_time.strftime('%d.%m.%Y %H:%M')}</p>
            <p><strong>Место проведения:</strong> {order.ticket.event.place_data.address if order.ticket.event.place_data else "Не указано"}</p>
            <p><strong>QR-код:</strong></p>
            <img src="data:image/png;base64,{img_str}" alt="QR-код для заказа #{order.id}" style="width: 100px; height: 100px; display: block; margin: 0 auto;">
        </div>
        """
        total_amount += order.total_price

    message = f"""\n    <html>
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


def send_ticket_notification(user, order, request=None):
    subject = "Ваш электронный билет"
    activation_link = None
    if request:
        activation_link = request.build_absolute_uri(
            reverse("activate_account", args=[user.pk])
        )

    # Формируем ссылку на скачивание билета
    ticket_download_url = ""
    if request:
        ticket_download_url = request.build_absolute_uri(
            reverse("event_detail", args=[order.ticket.event.id])
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
        button_text = "Перейти в личный кабинет для просмотра билета"
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

    message = f"""
    <html>
    <body>
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <h2 style="color: #2c3e50;">Здравствуйте, {user.get_full_name() or user.email}!</h2>
            
            <p>Благодарим вас за покупку билета на мероприятие:</p>
            <h3 style="color: #3498db;">{order.ticket.event.title}</h3>
            
            <div style="background-color: #f8f9fa; padding: 15px; border-radius: 5px; margin: 20px 0;">
                <p><strong>Тип билета:</strong> {order.ticket.name}</p>
                <p><strong>Количество:</strong> {order.quantity}</p>
                <p><strong>Сумма:</strong> {order.total_price} ₽</p>
                <p><strong>Дата и время:</strong> {order.ticket.event.date_time.strftime('%d.%m.%Y %H:%M')}</p>
                <p><strong>Место проведения:</strong> {order.ticket.event.place}</p>
            </div>
            
            <div style="text-align: center; margin: 30px 0;">
                <a href="{ticket_download_url}" style="
                    display: inline-block;
                    padding: 12px 24px;
                    background-color: #2ecc71;
                    color: white;
                    text-decoration: none;
                    border-radius: 4px;
                    font-weight: bold;
                ">Скачать билет (PDF)</a>
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


def send_partner_all_tickets_sold_notification(event):
    """
    Отправляет уведомление партнёру о том, что все билеты на мероприятие выкуплены.
    """
    subject = f"Все билеты на мероприятие '{event.title}' выкуплены"
    organizer_email = event.organizer.email

    # Формируем сообщение
    message = f"""
    <html>
    <body>
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <h2 style="color: #2c3e50;">Здравствуйте, {event.organizer.get_full_name()}!</h2>

            <p>Поздравляем! Все билеты на ваше мероприятие <strong>{event.title}</strong> были успешно выкуплены.</p>

            <div style="background-color: #f8f9fa; padding: 15px; border-radius: 5px; margin: 20px 0;">
                <p><strong>Дата и время:</strong> {event.date_time.strftime('%d.%m.%Y %H:%M')}</p>
                <p><strong>Место проведения:</strong> {event.get_place_address}</p>
            </div>

            <p>Теперь вы можете подготовиться к проведению мероприятия.</p>

            <div style="
                margin-top: 40px;
                padding-top: 20px;
                border-top: 1px solid #eee;
                font-size: 12px;
                color: #7f8c8d;
            ">
                <p>Если у вас возникли вопросы, обратитесь в нашу <a href="#">службу поддержки</a>.</p>
            </div>
        </div>
    </body>
    </html>
    """

    send_mail(
        subject,
        "",
        "dim.anosoff2018@yandex.ru",
        [organizer_email],
        html_message=message,
    )


def activate_account(request, pk):
    user = get_object_or_404(CustomUser, pk=pk)
    if request.method == "POST":
        password = request.POST.get("password")
        user.set_password(password)
        user.user_type = "visitor"  # Меняем статус на посетителя
        user.save()
        return redirect("login")
    return render(request, "activate_account.html")
