from django.shortcuts import (
    render,
    redirect,
    get_object_or_404,
    HttpResponseRedirect,
    reverse,
)
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth import logout as auth_logout
from .forms import CustomAuthenticationForm, CustomUserCreationForm
from django.views.decorators.cache import never_cache
from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate
from .forms import CustomAuthenticationForm
from .models import Event, Ticket
from django.contrib.auth.decorators import login_required, user_passes_test
from core.forms import SupportTicketForm
from .models import SupportTicket, SupportMessage, SupportAttachment
from django import forms

# require_POST
from django.views.decorators.http import require_POST


@never_cache
def login_view(request):
    if request.user.is_authenticated:
        # Если пользователь уже вошел, сразу редиректим его в нужный кабинет
        if request.user.user_type == "partner":
            return redirect("partner:dashboard")
        else:
            return redirect("visitor:dashboard")

    if request.method == "POST":
        form = CustomAuthenticationForm(request.POST)
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


@never_cache
def register_view(request):
    """Обрабатывает регистрацию нового пользователя."""
    if request.method == "POST":
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()  # Сохраняем пользователя в БД
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

        if new_subject and new_message:
            # Создаем новый тикет
            ticket = SupportTicket.objects.create(
                subject=new_subject, user=request.user, status="new"
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

    context = {
        "tickets": tickets,
        "selected_ticket": selected_ticket,
        "chat_messages": chat_messages,
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
    return render(request, "events/event_list.html", {"events": active_events})

def event_detail(request, event_id):
    event = get_object_or_404(Event, id=event_id)
    return render(request, "events/event_detail.html", {"event": event})

def buy_ticket(request, event_id):
    event = get_object_or_404(Event, id=event_id)
    # Здесь будет логика покупки билета
    return redirect("event_detail", event_id=event_id)