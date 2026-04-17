from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from core.models import Event, Ticket, Order, PayoutRequest
from django.db.models import Sum, Count, Avg, F, ExpressionWrapper, DecimalField
from .forms import EventForm, DocumentUploadForm
from core.forms import PartnerProfileForm, PasswordChangeForm
from django.core.mail import send_mail


@login_required
def partner_dashboard(request):
    if request.user.user_type != "partner":
        return redirect("visitor:dashboard")

    # Логика для партнера
    context = {"user": request.user}
    return render(request, "partner/dashboard.html", context)


@login_required
def create_event(request):
    """
    View для создания нового мероприятия.
    Видео обрабатывается в фоновом режиме через Celery.
    """
    if request.method == "POST":
        form = EventForm(request.POST, request.FILES)
        if form.is_valid():
            event = form.save(commit=False)
            event.organizer = request.user
            event.status = "on_moderation"
            event.save()

            ticket_data = form.cleaned_data.get("ticket_types", "")
            for line in ticket_data.split("\n"):
                line = line.strip()
                if ":" in line:
                    try:
                        name, price, quantity = [
                            item.strip() for item in line.split(":", 2)
                        ]
                        Ticket.objects.create(
                            event=event,
                            name=name,
                            price=float(price.replace(",", ".")),
                            available_quantity=int(quantity),
                        )
                    except (ValueError, TypeError):
                        continue
            return redirect("partner:dashboard")
    else:
        form = EventForm()

    return render(request, "partner/event_form.html", {"form": form})


def notify_organizer(event):
    subject = f"Ваше мероприятие '{event.title}' одобрено!"
    message = f"Привет, {event.organizer.first_name}!\n\nВаше мероприятие '{event.title}' успешно добавлено на сайт."
    send_mail(subject, message, "dim.anosoff2018@yandex.ru", [event.organizer.email])


def edit_event(request, event_id):
    """
    View для редактирования мероприятия.
    """
    # Получаем мероприятие по ID или выдаем 404 ошибку, если его нет
    event = get_object_or_404(Event, id=event_id, organizer=request.user)

    if request.method == "POST":
        form = EventForm(request.POST, request.FILES, instance=event)

        # Устанавливаем флаг изменения видео на основе данных формы
        if "video_changed" in request.POST and request.POST["video_changed"] == "True":
            event._video_changed = True
        else:
            event._video_changed = False

        if form.is_valid():
            # Сохраняем основные данные мероприятия
            event = form.save()

            # Обрабатываем данные о билетах из таблицы
            ticket_names = request.POST.getlist("ticket_name[]")
            ticket_prices = request.POST.getlist("ticket_price[]")
            ticket_quantities = request.POST.getlist("ticket_quantity[]")

            # Очищаем существующие билеты и создаем новые
            event.tickets.all().delete()

            for name, price, quantity in zip(
                ticket_names, ticket_prices, ticket_quantities
            ):
                if name and price and quantity:  # Проверяем, что все поля заполнены
                    try:
                        event.tickets.create(
                            name=name,
                            price=(
                                float(price.replace(",", "."))
                                if "," in price
                                else float(price)
                            ),
                            available_quantity=int(quantity),
                        )
                    except (ValueError, TypeError):
                        continue

            return redirect("partner:partner_event_list")
    else:
        # При GET-запросе заполняем форму данными из БД
        form = EventForm(instance=event)

    return render(request, "partner/event_form.html", {"form": form, "is_edit": True})


@login_required
def partner_event_list(request):
    """
    Отображает список всех мероприятий текущего партнера.
    """
    # Получаем все мероприятия, где организатор - это текущий пользователь
    events = Event.objects.filter(organizer=request.user).order_by("-date_time")

    event_data = []
    for event in events:
        # Суммируем количество проданных билетов по всем типам этого мероприятия
        sold = sum(ticket.orders.count() for ticket in event.tickets.all())
        # Суммируем общее количество доступных билетов
        total = sum(ticket.available_quantity for ticket in event.tickets.all())

        event_data.append(
            {
                "event": event,
                "sold": sold,
                "total": total,
            }
        )

    context = {
        "events": event_data,
    }
    return render(request, "partner/partner_event_list.html", context)


@login_required
def reports(request):
    """
    Отчеты и статистика продаж для партнера.
    """
    orders = Order.objects.filter(ticket__event__organizer=request.user)

    # Расчет общей статистики
    total_sales = orders.aggregate(total=Sum("total_price"))["total"] or 0
    tickets_sold = orders.aggregate(count=Count("id"))["count"] or 0
    avg_check = orders.aggregate(avg=Avg("total_price"))["avg"] or 0

    sales_graph_data = {
        "2026-04-01": 15000,
        "2026-04-02": 25000,
        "2026-04-03": 35000,
        "2026-04-04": 10000,
    }

    context = {
        "total_sales": total_sales,
        "tickets_sold": tickets_sold,
        "avg_check": avg_check,
        "sales_graph_data": sales_graph_data,
    }
    return render(request, "partner/reports.html", context)


@login_required
def participant_list(request, event_id):
    """
    Список участников для выбранного мероприятия.
    """
    # Получаем мероприятие или выдаем 404, если его нет или оно чужое
    event = get_object_or_404(Event, id=event_id, organizer=request.user)

    orders = Order.objects.filter(ticket__event=event).select_related("ticket")

    context = {
        "event": event,
        "orders": orders,
    }
    return render(request, "partner/participant_list.html", context)


@login_required
def finances(request):
    orders = Order.objects.filter(ticket__event__organizer=request.user)

    # Считаем общую выручку
    total_revenue = orders.aggregate(total=Sum("total_price"))["total"] or 0

    commission_sum = (
        orders.annotate(
            event_commission=ExpressionWrapper(
                F("total_price") * (F("ticket__event__commission_rate") / 100),
                output_field=DecimalField(),
            )
        ).aggregate(total_commission=Sum("event_commission"))["total_commission"]
        or 0
    )
    commission_amount = commission_sum
    payout_amount = total_revenue - commission_sum

    payout_history = PayoutRequest.objects.filter(organizer=request.user).order_by(
        "-created_at"
    )

    context = {
        "total_revenue": total_revenue,
        "commission_amount": commission_amount,
        "payout_amount": payout_amount,
        "payout_history": payout_history,
    }
    return render(request, "partner/finances.html", context)


@login_required
def profile_edit(request):
    if request.method == "POST":
        # Обработка основной формы профиля
        user_form = PartnerProfileForm(
            request.POST, request.FILES, instance=request.user
        )
        if user_form.is_valid():
            user_form.save()

            # Обработка формы смены пароля (если она была отправлена)
            password_form = PasswordChangeForm(user=request.user, data=request.POST)
            if password_form.is_valid():
                password_form.save()
                update_session_auth_hash(
                    request, password_form.user
                )  # Чтобы не разлогинить пользователя

        # Обработка формы загрузки документов
        if "upload_documents" in request.POST:
            # Проверяем, что у пользователя нет документов на рассмотрении
            if request.user.verification_status == "not_submitted":
                document_form = DocumentUploadForm(
                    request.POST, request.FILES, user=request.user
                )
                if document_form.is_valid():
                    document_form.save()
                    request.user.verification_status = "pending"
                    request.user.save()

        return redirect("partner:profile_edit")

    else:
        user_form = PartnerProfileForm(instance=request.user)
        password_form = PasswordChangeForm(user=request.user)
        document_form = DocumentUploadForm(user=request.user)

    context = {
        "user_form": user_form,
        "password_form": password_form,
        "document_form": document_form,
    }
    return render(request, "partner/profile_edit.html", context)
