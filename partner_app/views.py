from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.core.files.base import ContentFile
from core.models import Event, Ticket, Order, PayoutRequest
from django.db.models import Sum, Count, Avg, F, ExpressionWrapper, DecimalField
from django.db.models.functions import TruncDate
from .forms import EventForm, DocumentUploadForm
from .models import SalesReport
from .utils import generate_sales_report
from core.forms import PartnerProfileForm, PasswordChangeForm
from django.core.mail import send_mail, EmailMessage
from django.utils import timezone
from datetime import datetime, timedelta
import os

# The above code is a Python script that includes a comment indicating the purpose of the code
# ("date"). However, the code itself is missing and only contains comment lines.
from datetime import datetime


@login_required
def partner_dashboard(request):
    if request.user.user_type != "partner":
        return redirect("visitor:dashboard")

    # Получаем активные мероприятия партнёра
    active_events = Event.objects.filter(
        organizer=request.user,
        status="active"
    ).count()

    # Получаем продажи за текущий месяц
    from datetime import datetime
    current_month = datetime.now().month
    current_year = datetime.now().year

    monthly_sales = Order.objects.filter(
        ticket__event__organizer=request.user,
        created_at__year=current_year,
        created_at__month=current_month
    ).aggregate(total=Sum("total_price"))["total"] or 0

    # Получаем ожидающие выплаты
    pending_payouts = PayoutRequest.objects.filter(
        organizer=request.user,
        status="pending"
    ).count()

    context = {
        "user": request.user,
        "active_events_count": active_events,
        "monthly_sales_sum": monthly_sales,
        "pending_payouts_count": pending_payouts,
    }
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

            # Обрабатываем данные о билетах из таблицы
            ticket_names = request.POST.getlist("ticket_name[]")
            ticket_prices = request.POST.getlist("ticket_price[]")
            ticket_quantities = request.POST.getlist("ticket_quantity[]")

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
            return redirect("partner:dashboard")
    else:
        form = EventForm()

    return render(request, "partner/event_form.html", {"form": form, "is_edit": False})


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
    Отображает список всех мероприятий текущего партнера с возможностью фильтрации.
    """
    # Получаем параметры фильтрации из GET-запроса
    title_query = request.GET.get("title", None)
    date_query = request.GET.get("date", None)

    # Базовый фильтр: только мероприятия текущего пользователя
    events = Event.objects.filter(organizer=request.user)

    # Применяем фильтры
    if title_query:
        events = events.filter(title__icontains=title_query)
    if date_query:
        # Преобразуем строку даты в объект date для фильтрации
        try:
            query_date = datetime.fromisoformat(date_query)
            events = events.filter(date_time__date=query_date)
        except (ValueError, TypeError):
            # Если дата некорректна, игнорируем этот фильтр
            pass

    # Сортируем по дате (новые сверху)
    events = events.order_by("-date_time")

    event_data = []
    for event in events:
        # Суммируем количество проданных билетов по всем типам этого мероприятия
        sold_tickets = sum(order.quantity for ticket in event.tickets.all() for order in ticket.orders.all())
        # Суммируем общее количество доступных билетов
        total = sum(ticket.available_quantity for ticket in event.tickets.all())

        event_data.append(
            {
                "event": event,
                "sold": sold_tickets,
                "total": total,
            }
        )

    context = {
        "events": event_data,
    }
    return render(request, "partner/partner_event_list.html", context)


@login_required
def duplicate_event(request, event_id):
    """
    Дублирует мероприятие.
    """
    event = get_object_or_404(Event, id=event_id, organizer=request.user)

    # Создаем копию мероприятия
    new_event = Event(
        organizer=event.organizer,
        title=f"Копия: {event.title}",
        description_short=event.description_short,
        description_full=event.description_full,
        date_time=event.date_time,
        place=event.place,
        status="on_moderation",  # Новое мероприятие должно пройти модерацию
        image=event.image,
        category=event.category,
        video_url=event.video_url,
        program_file=event.program_file,
        allow_booking_without_payment=event.allow_booking_without_payment,
        auto_close_sales_hours=event.auto_close_sales_hours,
        commission_rate=event.commission_rate,
    )
    new_event.save()

    # Копируем билеты
    for ticket in event.tickets.all():
        Ticket.objects.create(
            event=new_event,
            name=ticket.name,
            price=ticket.price,
            available_quantity=ticket.available_quantity,
        )

    return redirect("partner:partner_event_list")


@login_required
def delete_event(request, event_id):
    """
    Удаляет мероприятие и связанные медиафайлы.
    """
    event = get_object_or_404(Event, id=event_id, organizer=request.user)

    if request.method == "POST":
        # Удаляем медиафайлы, если они существуют
        if event.image:
            event.image.delete()
        if event.video_url:
            event.video_url.delete()
        if event.program_file:
            event.program_file.delete()

        event.delete()
        return redirect("partner:partner_event_list")

    return render(
        request,
        "partner/event_confirm_delete.html",
        {"event": event},
    )


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

    # Получаем данные для графика продаж по дням
    sales_graph_data = (
        orders.annotate(date=TruncDate("created_at"))
        .values("date")
        .annotate(total=Sum("total_price"))
        .order_by("date")
    )

    # Преобразуем в формат для Chart.js
    sales_graph_data = {
        item["date"].strftime("%Y-%m-%d"): item["total"]
        for item in sales_graph_data
    }

    # Получаем список ранее сгенерированных отчётов
    user_reports = SalesReport.objects.filter(partner=request.user).order_by("-created_at")

    context = {
        "total_sales": total_sales,
        "tickets_sold": tickets_sold,
        "avg_check": avg_check,
        "sales_graph_data": sales_graph_data,
        "user_reports": user_reports,
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

@login_required
def generate_report(request):
    """
    Генерирует отчёт о продажах за указанный период в выбранном формате.
    """
    if request.method == "POST":
        period_start = request.POST.get("period_start")
        period_end = request.POST.get("period_end")
        report_type = request.POST.get("report_type")

        try:
            period_start = datetime.strptime(period_start, "%Y-%m-%d").date()
            period_end = datetime.strptime(period_end, "%Y-%m-%d").date()
        except ValueError:
            return JsonResponse(
                {"status": "error", "message": "Неверный формат даты"},
                status=400,
            )

        try:
            # Генерируем отчёт
            report_file = generate_sales_report(
                request.user, period_start, period_end, report_type
            )

            # Сохраняем отчёт в модели
            report = SalesReport.objects.create(
                partner=request.user,
                period_start=period_start,
                period_end=period_end,
                report_type=report_type,
                status="completed",
            )

            # Сохраняем файл
            if report_type == "csv":
                file_name = f"report_{period_start}_{period_end}.csv"
                report.file_path.save(
                    file_name,
                    ContentFile(report_file.getvalue().encode("utf-8")),
                )
            else:
                file_name = f"report_{period_start}_{period_end}.{report_type}"
                report.file_path.save(
                    file_name,
                    ContentFile(report_file.getvalue()),
                )

            # Возвращаем ссылку на скачивание
            return JsonResponse(
                {
                    "status": "success",
                    "download_url": report.file_path.url,
                }
            )

        except Exception as e:
            return JsonResponse(
                {"status": "error", "message": str(e)},
                status=500,
            )

    return JsonResponse(
        {"status": "error", "message": "Неверный метод запроса"},
        status=405,
    )
