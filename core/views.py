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
from .models import Event, Ticket, Tag, MainTag
from django.contrib.auth.decorators import login_required, user_passes_test
from core.forms import SupportTicketForm
from django.utils import timezone
from .models import SupportTicket, SupportMessage, SupportAttachment, CustomUser, Order, MainTag
from django import forms
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth import update_session_auth_hash
from .models import EmailVerificationCode
from django.views.decorators.http import require_POST
from django.core.mail import send_mail
from django.contrib.auth.hashers import make_password
from django.views.decorators.http import require_http_methods
from django.contrib import messages
from django.template.loader import render_to_string
from django.utils.html import strip_tags
import uuid
from django.utils import timezone
import logging
import random
import string
import requests
import json
import base64
import qrcode
import io
import datetime
from django.db.models import Sum, F, ExpressionWrapper, DecimalField, Count, Q
from django.db.models.functions import Coalesce
from django.contrib.admin.views.decorators import staff_member_required
# transaction
from django.db import transaction
from venues.models import Venue
logger = logging.getLogger(__name__)


def landing_page(request):
    active_events = (
        Event.objects.filter(status="active")
        .select_related("organizer", "category")
        .prefetch_related("images")
        .order_by("date_time")
    )

    # Получаем выбранные значения фильтров из GET-запроса
    selected_category = request.GET.get("category", "")
    selected_date_from = request.GET.get("date_from", "")
    selected_date_to = request.GET.get("date_to", "")
    search_title = request.GET.get("title", "").strip()

    # Применяем фильтры
    if selected_category:
        active_events = active_events.filter(category__id=selected_category)
    if selected_date_from:
        try:
            from datetime import datetime, timedelta
            date_from = datetime.strptime(selected_date_from, "%Y-%m-%d")
            active_events = active_events.filter(date_time__gte=date_from)
        except ValueError:
            pass
    if selected_date_to:
        try:
            from datetime import datetime, timedelta
            date_to = datetime.strptime(selected_date_to, "%Y-%m-%d")
            active_events = active_events.filter(date_time__lte=date_to + timedelta(days=1))
        except ValueError:
            pass
    if search_title:
        active_events = active_events.filter(title__icontains=search_title)

    # Get published venues for the carousel
    active_venues = (
        Venue.objects.filter(status="published")
        .select_related("venue_type")
        .prefetch_related("images")
        .order_by("-tariff", "title")[:10]
    )

    # Получаем все категории для выпадающего списка
    from core.models import Category
    categories = Category.objects.all().order_by("name")

    return render(
        request,
        "landing.html",
        {
            "active_events": active_events,
            "active_venues": active_venues,
            "categories": categories,
            "selected_category": selected_category,
            "selected_date_from": selected_date_from,
            "selected_date_to": selected_date_to,
            "search_title": search_title,
        },
    )

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
            user = form.save(commit=False)  # Сохраняем пользователя в БД, но не коммитим
            user.backend = "core.backends.EmailBackend"
            user.save()

            # Отправляем код подтверждения на почту
            form.send_verification_code(request)

            # Сохраняем пользователя в сессии для дальнейшего подтверждения
            request.session['unverified_user_id'] = user.id

            # Редирект на страницу ввода кода подтверждения
            return redirect("verify_email")
    else:
        form = CustomUserCreationForm()

    return render(request, "registration/register.html", {"form": form})

def verify_email_view(request):
    """Обрабатывает ввод кода подтверждения."""
    if 'unverified_user_id' not in request.session:
        return redirect('login')

    user_id = request.session['unverified_user_id']
    user = get_object_or_404(CustomUser, id=user_id)

    if request.method == "POST":
        code1 = request.POST.get("code1")
        code2 = request.POST.get("code2")
        code3 = request.POST.get("code3")
        code4 = request.POST.get("code4")
        code5 = request.POST.get("code5")

        entered_code = f"{code1}{code2}{code3}{code4}{code5}"

        # Проверяем код
        from .models import EmailVerificationCode
        verification_code = EmailVerificationCode.objects.filter(
            user=user,
            code=entered_code,
            is_used=False
        ).first()

        if verification_code:
            # Код верный, подтверждаем пользователя
            user.is_verified = True
            user.save()

            # Помечаем код как использованный
            verification_code.is_used = True
            verification_code.save()

            # Логиним пользователя
            user.backend = "core.backends.EmailBackend"
            login(request, user)

            # Очищаем сессию
            if 'unverified_user_id' in request.session:
                del request.session['unverified_user_id']

            # Редирект в зависимости от роли
            if user.user_type == "partner":
                return redirect("partner:dashboard")
            else:
                return redirect("visitor:dashboard")
        else:
            # Код неверный
            return render(request, "registration/verify_email.html", {
                "error_message": "Неверный код подтверждения. Пожалуйста, попробуйте еще раз."
            })

    return render(request, "registration/verify_email.html")

@require_POST
def resend_verification_code(request):
    """Повторная отправка кода подтверждения."""
    if 'unverified_user_id' not in request.session:
        return JsonResponse({'success': False, 'message': 'Сессия истекла. Пожалуйста, начните регистрацию заново.'}, status=400)

    user_id = request.session['unverified_user_id']
    user = get_object_or_404(CustomUser, id=user_id)

    # Делаем все предыдущие коды недействительными
    from .models import EmailVerificationCode
    EmailVerificationCode.objects.filter(user=user, is_used=False).update(is_used=True)

    # Отправляем новый код
    from .forms import CustomUserCreationForm
    form = CustomUserCreationForm(instance=user)
    form.send_verification_code(request)

    return JsonResponse({'success': True, 'message': 'Код подтверждения был успешно отправлен повторно.'})

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
    selected_ticket = None
    chat_messages = []

    # Получаем event_id из GET-запроса
    event_id = request.GET.get("event_id")

    # Если пользователь - партнёр, показываем тикеты, связанные с его мероприятиями
    if request.user.user_type == "partner":
        tickets = SupportTicket.objects.filter(
            Q(user=request.user) | Q(event__organizer=request.user)
        ).order_by("-created_at")
    else:
        # Для обычных пользователей показываем тикеты, связанные с их email
        tickets = SupportTicket.objects.filter(
            Q(user=request.user) | Q(user__email=request.user.email)
        ).order_by("-created_at")

    if request.GET.get("ticket_id"):
        ticket_id = request.GET.get("ticket_id")
        selected_ticket = get_object_or_404(SupportTicket, id=ticket_id)
        chat_messages = selected_ticket.messages.all()
    # Если указан event_id, фильтруем тикеты по мероприятию
    elif event_id:
        tickets = tickets.filter(event_id=event_id)

    # Получаем мероприятия пользователя для формы создания тикета
    if request.user.user_type == "partner":
        # Для партнёров показываем все их мероприятия
        user_events = Event.objects.filter(organizer=request.user)
    else:
        # Для обычных пользователей показываем только мероприятия с проданными билетами
        user_events = (
            Event.objects.filter(organizer=request.user, has_sold_tickets=True)
            if request.user.user_type != "visitor"
            else []
        )

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
    active_events = (
        Event.objects.filter(status="active")
        .select_related("organizer", "category", "format")
        .prefetch_related("images", "tags")
        .order_by("date_time")
    )
    # Получаем все основные теги с их подтегами
    main_tags = MainTag.objects.prefetch_related('subtags').all()

    # Получаем выбранные теги из GET-запроса
    selected_tags = request.GET.getlist("tags")

    # Фильтруем мероприятия по выбранным тегам, если они есть
    if selected_tags:
        active_events = active_events.filter(tags__name__in=selected_tags).distinct()

    # Получаем значения фильтров из GET-запроса
    selected_category = request.GET.get("category", "")
    selected_format = request.GET.get("format", "")
    selected_date_from = request.GET.get("date_from", "")
    selected_date_to = request.GET.get("date_to", "")
    search_title = request.GET.get("title", "").strip()

    # Применяем фильтры
    if selected_category:
        active_events = active_events.filter(category__id=selected_category)
    if selected_format:
        active_events = active_events.filter(format__id=selected_format)
    if selected_date_from:
        try:
            from datetime import datetime, timedelta
            date_from = datetime.strptime(selected_date_from, "%Y-%m-%d")
            # Если выбрана только дата "с", фильтруем >= этой даты
            if not selected_date_to or selected_date_from == selected_date_to:
                # Одна дата — показываем только мероприятия этого дня
                date_to = date_from + timedelta(days=1)
                active_events = active_events.filter(date_time__gte=date_from, date_time__lt=date_to)
            else:
                # Диапазон дат — фильтруем >= date_from
                active_events = active_events.filter(date_time__gte=date_from)
        except ValueError:
            pass
    if selected_date_to and selected_date_from != selected_date_to:
        try:
            from datetime import datetime, timedelta
            date_to = datetime.strptime(selected_date_to, "%Y-%m-%d")
            # Добавляем один день, чтобы включить всю конечную дату в диапазоне
            active_events = active_events.filter(date_time__lte=date_to + timedelta(days=1))
        except ValueError:
            pass
    if search_title:
        active_events = active_events.filter(title__icontains=search_title)

    # Получаем все категории и форматы для выпадающих списков
    from core.models import Category, Format
    categories = Category.objects.all().order_by("name")
    formats = Format.objects.all().order_by("name")

    return render(
        request,
        "events/event_list.html",
        {
            "active_events": active_events,
            "main_tags": main_tags,
            "selected_tags": selected_tags,
            "categories": categories,
            "formats": formats,
            "selected_category": selected_category,
            "selected_format": selected_format,
            "selected_date_from": selected_date_from,
            "selected_date_to": selected_date_to,
            "search_title": search_title,
        },
    )

def event_detail(request, event_id):
    event = get_object_or_404(Event, id=event_id)
    tickets = event.tickets.all()
    return render(request, "events/event_detail.html", {"event": event, "tickets": tickets})

@require_http_methods(["GET", "POST"])
def handle_platform_request(request, event, user, ticket, quantity):
    """
    Обработка заявки на участие в мероприятии (отправка организатору).
    Используется когда purchase_type = "platform_request"
    """
    question = request.POST.get("question", "")

    # Создаем заявку в поддержку
    from core.models import SupportTicket, SupportMessage

    ticket_request = SupportTicket.objects.create(
        user=user,
        subject=f"Заявка на участие в мероприятии: {event.title}",
        event=event,
    )

    # Создаем первое сообщение с вопросом
    SupportMessage.objects.create(
        ticket=ticket_request,
        user=user,
        is_from_user=True,
        text=f"Вопрос от участника:\n{question}",
    )

    return JsonResponse(
        {
            "success": True,
            "message": "Ваша заявка успешно отправлена организатору. Мы свяжемся с вами в ближайшее время.",
        }
    )

@require_http_methods(["GET", "POST"])
def send_event_request(request, event_id, question=""):
    """
    Обработка заявки на участие в мероприятии (отправка организатору).
    Используется когда purchase_type = "platform_request"
    """
    event = get_object_or_404(Event, id=event_id)

    if request.method == "GET":
        return redirect("event_detail", event_id=event_id)

    # Получаем данные из формы
    email = (request.POST.get("email") or "").strip()
    first_name = (request.POST.get("first_name") or "").strip()
    last_name = (request.POST.get("last_name") or "").strip()
    phone = (request.POST.get("phone") or "").strip()

    # Используем переданный вопрос или берем из POST
    question = question or request.POST.get("question", "")

    # Создаём или получаем пользователя по email
    user, created = CustomUser.objects.get_or_create(
        email=email,
        defaults={
            "first_name": first_name,
            "last_name": last_name,
            "user_type": "guest",
            "username": email,
        },
    )

    # Обновляем данные пользователя, если он уже существовал
    if not created:
        user.first_name = first_name
        user.last_name = last_name
        user.save()

    if created:
        user.set_unusable_password()
        user.save()

    try:
        with transaction.atomic():
            # Создаем заявку в поддержку
            from core.models import SupportTicket, SupportMessage

            ticket = SupportTicket.objects.create(
                user=user,
                subject=f"Заявка на участие в мероприятии: {event.title}",
                event=event,
            )

            # Создаем первое сообщение с вопросом
            SupportMessage.objects.create(
                ticket=ticket,
                user=user,
                is_from_user=True,
                text=f"Вопрос от участника:\n{question}",
            )

            # Проверяем, является ли запрос AJAX
            is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest"
            if is_ajax:
                return JsonResponse(
                    {
                        "success": True,
                        "message": "Ваша заявка успешно отправлена организатору. Мы свяжемся с вами в ближайшее время.",
                        "request_id": ticket.id,
                    }
                )
            else:
                messages.success(
                    request,
                    "Ваша заявка успешно отправлена организатору. Мы свяжемся с вами в ближайшее время.",
                )
                return redirect("event_detail", event_id=event_id)

    except Exception as e:
        logger.error(f"Ошибка при создании заявки: {str(e)}")
        if is_ajax:
            return JsonResponse(
                {
                    "success": False,
                    "message": "Произошла ошибка при отправке заявки. Пожалуйста, попробуйте еще раз.",
                },
                status=500,
            )
        else:
            messages.error(
                request,
                "Произошла ошибка при отправке заявки. Пожалуйста, попробуйте еще раз.",
            )
            return redirect("event_detail", event_id=event_id)

def activate_account(request, pk):
    user = get_object_or_404(CustomUser, pk=pk)
    if request.method == "POST":
        password = request.POST.get("password")
        user.set_password(password)
        user.user_type = "visitor"  # Меняем статус на посетителя
        user.save()
        return redirect("login")
    return render(request, "activate_account.html")

@staff_member_required
def sales_register(request):
    """
    Формирует реестр продаж по всем партнёрам за указанный период.
    Доступно только для сотрудников (администраторов).
    """
    if request.method == "POST":
        start_date_str = request.POST.get("start_date")
        end_date_str = request.POST.get("end_date")

        try:
            start_date = timezone.datetime.strptime(start_date_str, "%Y-%m-%d")
            end_date = timezone.datetime.strptime(end_date_str, "%Y-%m-%d")
        except ValueError:
            messages.error(
                request, "Некорректный формат даты. Используйте формат YYYY-MM-DD."
            )
            return redirect("sales_register")

        # Получаем всех партнёров
        partners = CustomUser.objects.filter(user_type="partner")
        register_data = []

        for partner in partners:
            # Формируем реестр продаж для каждого партнёра
            sales_register = generate_sales_register(partner, start_date, end_date)
            print(
                f"Partner: {partner.email}, Sales: {sales_register['total_sales']}"
            )  # Отладочный вывод
            if sales_register["total_sales"] > 0:  # Только если есть продажи
                register_data.append(
                    {
                        "partner": partner,
                        "total_sales": sales_register["total_sales"],
                        "total_commission": sales_register["total_commission"],
                        "total_refunds": sales_register["total_refunds"],
                        "net_amount": sales_register["net_amount"],
                        "orders": sales_register["orders"],
                    }
                )

        print(f"Total partners with sales: {len(register_data)}")  # Отладочный вывод
        context = {
            "register_data": register_data,
            "start_date": start_date,
            "end_date": end_date,
        }
        return render(request, "admin/sales_register.html", context)
    return render(request, "admin/sales_register_form.html")

def generate_sales_register(partner, start_date, end_date):
    """
    Формирует реестр продаж для партнёра за указанный период.

    Args:
        partner: Объект пользователя (CustomUser), для которого формируется реестр.
        start_date: Начальная дата периода (datetime).
        end_date: Конечная дата периода (datetime).

    Returns:
        dict: Словарь с данными реестра:
            - total_sales: Общая сумма продаж (без учёта комиссии).
            - total_commission: Общая сумма удержанной комиссии.
            - total_refunds: Общая сумма возвратов.
            - net_amount: Чистая сумма к выплате (total_sales - total_commission - total_refunds).
            - orders: Список заказов с детализацией.
    """
    # Получаем все мероприятия партнёра
    partner_events = Event.objects.filter(organizer=partner)

    # Получаем все заказы для этих мероприятий за указанный период
    orders = Order.objects.filter(
        ticket__event__in=partner_events,
        created_at__gte=start_date,
        created_at__lte=end_date,
        is_paid=True,  # Только оплаченные заказы
    ).select_related("ticket__event")

    # Рассчитываем общие суммы (исключаем возвраты из выручки и комиссии)
    non_refunded_orders = orders.exclude(payment_status__in=["canceled", "refunded"])

    total_sales = non_refunded_orders.aggregate(
        total=Coalesce(Sum("total_price"), 0, output_field=DecimalField())
    )["total"]

    total_commission = non_refunded_orders.aggregate(
        total=Coalesce(Sum("platform_commission"), 0, output_field=DecimalField())
    )["total"]

    # Рассчитываем сумму возвратов: учитываем заказы, которые были оплачены, но потом возвращены или отменены
    refunded_orders = Order.objects.filter(
        ticket__event__in=partner_events,
        created_at__gte=start_date,
        created_at__lte=end_date,
        payment_status__in=["canceled", "refunded"],
    )

    total_refunds = refunded_orders.aggregate(
        total=Coalesce(Sum("total_price"), 0, output_field=DecimalField())
    )["total"]

    # Чистая сумма к выплате (возвраты уже исключены из выручки и комиссии)
    net_amount = total_sales - total_commission

    return {
        "total_sales": total_sales,
        "total_commission": total_commission,
        "total_refunds": total_refunds,
        "net_amount": net_amount,
        "orders": orders,
        "start_date": start_date,
        "end_date": end_date,
    }