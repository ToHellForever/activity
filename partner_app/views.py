from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.core.files.base import ContentFile
from django.core.mail import send_mail, EmailMessage
from django.utils import timezone
from django.db.models import Sum, Count, Avg, F, ExpressionWrapper, DecimalField
from django.db.models.functions import TruncDate
from django.contrib import messages
import logging

logger = logging.getLogger(__name__)
from datetime import datetime, timedelta
import os
import json

from core.models import Event, Ticket, Order, PayoutRequest
from .forms import EventForm, DocumentUploadForm, ReportScheduleForm
from .models import SalesReport, ReportSchedule
from .utils import generate_sales_report
from core.forms import PartnerProfileForm, PasswordChangeForm


@login_required
def partner_dashboard(request):
    if request.user.user_type != "partner":
        return redirect("visitor:dashboard")

    # Получаем активные мероприятия партнёра
    active_events = Event.objects.filter(
        organizer=request.user, status="active"
    ).count()

    # Получаем продажи за текущий месяц
    from datetime import datetime

    current_month = datetime.now().month
    current_year = datetime.now().year

    monthly_sales = (
        Order.objects.filter(
            ticket__event__organizer=request.user,
            created_at__year=current_year,
            created_at__month=current_month,
        ).aggregate(total=Sum("total_price"))["total"]
        or 0
    )

    # Получаем ожидающие выплаты
    pending_payouts = PayoutRequest.objects.filter(
        organizer=request.user, status="pending"
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
            return redirect("partner:partner_event_list")
    else:
        form = EventForm()

    ticket_data = []
    if request.method == "POST" and not form.is_valid():
        # Сохраняем данные о билетах для повторного отображения при ошибках валидации
        ticket_data = [
            {"name": name, "price": price, "quantity": quantity}
            for name, price, quantity in zip(
                request.POST.getlist("ticket_name[]"),
                request.POST.getlist("ticket_price[]"),
                request.POST.getlist("ticket_quantity[]"),
            )
            if name and price and quantity
        ]

    return render(
        request,
        "partner/event_form.html",
        {
            "form": form,
            "is_edit": False,
            "ticket_data": ticket_data,
            "saved_media": (
                {
                    "image": request.FILES.get("image"),
                    "video_url": request.FILES.get("video_url"),
                    "program_file": request.FILES.get("program_file"),
                }
                if request.method == "POST"
                else {}
            ),
        },
    )


def notify_organizer(event):
    subject = f"Ваше мероприятие '{event.title}' одобрено!"
    message = f"Привет, {event.organizer.first_name}!\n\nВаше мероприятие '{event.title}' успешно добавлено на сайт."
    send_mail(subject, message, "dim.anosoff2018@yandex.ru", [event.organizer.email])


@login_required
def edit_event(request, event_id):
    """
    View для редактирования мероприятия.
    """
    # Получаем мероприятие по ID или выдаем 404 ошибку, если его нет
    event = get_object_or_404(Event, id=event_id, organizer=request.user)

    # Проверяем, можно ли редактировать мероприятие
    if event.has_sold_tickets:
        messages.error(
            request,
            "Редактирование этого мероприятия запрещено, так как на него уже проданы билеты. "
            "Пожалуйста, обратитесь в техническую поддержку для внесения изменений.",
        )
        return redirect("partner:partner_event_list")

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
        sold_tickets = sum(
            order.quantity
            for ticket in event.tickets.all()
            for order in ticket.orders.all()
        )
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
        place=event.place_data.get('address') if event.place_data else None,
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
def bulk_delete_events(request):
    """
    Удаляет несколько мероприятий за раз.
    """
    if request.method == "POST":
        event_ids = request.POST.getlist("event_ids")
        if not event_ids:
            messages.error(request, "Не выбрано ни одного мероприятия для удаления.")
            return redirect("partner:partner_event_list")

        deleted_count = 0
        for event_id in event_ids:
            try:
                event = Event.objects.get(id=event_id, organizer=request.user)

                # Получаем пути к файлам, чтобы удалить их напрямую
                image_path = event.image.path if event.image else None
                video_path = event.video_url.path if event.video_url else None
                program_file_path = (
                    event.program_file.path if event.program_file else None
                )

                # Удаляем объект без вызова save()
                event_id = event.id
                event.delete()

                # Удаляем файлы напрямую, если они существуют
                if image_path and os.path.exists(image_path):
                    os.remove(image_path)
                if video_path and os.path.exists(video_path):
                    os.remove(video_path)
                if program_file_path and os.path.exists(program_file_path):
                    os.remove(program_file_path)

                deleted_count += 1
            except Event.DoesNotExist:
                continue
            except Exception as e:
                logger.error(f"Ошибка при удалении мероприятия {event_id}: {str(e)}")
                continue

        messages.success(request, f"Успешно удалено {deleted_count} мероприятий.")
        return redirect("partner:partner_event_list")

    return redirect("partner:partner_event_list")


@login_required
def reports(request):
    """
    Отчеты и статистика продаж для партнера.
    """
    orders = Order.objects.filter(ticket__event__organizer=request.user)

    # Расчет общей статистики
    total_sales = orders.aggregate(total=Sum("total_price"))["total"] or 0
    # Считаем реальное количество проданных билетов (не заказов)
    tickets_sold = sum(order.quantity for order in orders)
    # Средний чек = общая выручка / количество проданных билетов
    avg_check = total_sales / tickets_sold if tickets_sold > 0 else 0

    # Получаем данные для графика продаж по дням
    sales_graph_data = (
        orders.annotate(date=TruncDate("created_at"))
        .values("date")
        .annotate(total=Sum("total_price"))
        .order_by("date")
    )

    # Преобразуем в формат для Chart.js (конвертируем Decimal в float)
    sales_graph_data = {
        item["date"].strftime("%Y-%m-%d"): float(item["total"])
        for item in sales_graph_data
    }

    # Получаем список ранее сгенерированных отчётов
    user_reports = SalesReport.objects.filter(partner=request.user).order_by(
        "-created_at"
    )

    # Получаем текущие настройки расписания отчётов
    try:
        report_schedule = ReportSchedule.objects.get(partner=request.user)
    except ReportSchedule.DoesNotExist:
        report_schedule = None

    context = {
        "total_sales": "{:,.2f}".format(total_sales).replace(",", " "),
        "tickets_sold": tickets_sold,
        "avg_check": "{:,.2f}".format(avg_check).replace(",", " "),
        "sales_graph_data": json.dumps(sales_graph_data),
        "user_reports": user_reports,
        "report_schedule": report_schedule,
    }
    return render(request, "partner/reports.html", context)


@login_required
def participant_list(request, event_id):
    """
    Список участников для выбранного мероприятия с поиском, фильтрацией и экспортом.
    """
    # Получаем мероприятие или выдаем 404, если его нет или оно чужое
    event = get_object_or_404(Event, id=event_id, organizer=request.user)

    # Получаем параметры фильтрации из GET-запроса
    search_name = request.GET.get("name", "")
    search_email = request.GET.get("email", "")
    search_status = request.GET.get("status", "")

    # Базовый фильтр: только заказы для этого мероприятия
    orders = Order.objects.filter(ticket__event=event).select_related("ticket")

    # Применяем фильтры
    if search_name:
        orders = orders.filter(participant_data__name__icontains=search_name)
    if search_email:
        orders = orders.filter(participant_data__email__icontains=search_email)
    if search_status == "attended":
        orders = orders.filter(attended=True)
    elif search_status == "not_attended":
        orders = orders.filter(attended=False)

    # Обработка экспорта
    export_format = request.GET.get("export")
    if export_format:
        return export_participant_list(orders, event, export_format)

    context = {
        "event": event,
        "orders": orders,
    }
    return render(request, "partner/participant_list.html", context)


def export_participant_list(orders, event, export_format):
    """
    Экспортирует список участников в Excel или PDF.
    """
    import io
    from django.http import HttpResponse

    if export_format == "excel":
        # Создаем Excel-файл
        import openpyxl
        from openpyxl.styles import Font, Alignment

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = f"Участники {event.title}"

        # Заголовки
        headers = [
            "Имя",
            "E-mail",
            "Телефон",
            "Дата покупки",
            "Тип билета",
            "Статус",
            "Цена",
        ]
        for col_num, header in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col_num, value=header)
            cell.font = Font(bold=True)
            cell.alignment = Alignment(horizontal="center")

        # Данные
        for row_num, order in enumerate(orders, 2):
            ws.cell(
                row=row_num,
                column=1,
                value=f"{order.participant_data.get('first_name', '')} {order.participant_data.get('last_name', '')}".strip(),
            )
            ws.cell(
                row=row_num, column=2, value=order.participant_data.get("email", "")
            )
            ws.cell(
                row=row_num, column=3, value=order.participant_data.get("phone", "")
            )
            ws.cell(
                row=row_num, column=4, value=order.created_at.strftime("%d.%m.%Y %H:%M")
            )
            ws.cell(row=row_num, column=5, value=order.ticket.name)
            ws.cell(
                row=row_num,
                column=6,
                value="Оплачено" if order.attended else "Ожидает оплаты",
            )
            ws.cell(row=row_num, column=7, value=f"{order.total_price:.2f} руб.")

        # Автоподбор ширины столбцов
        for column in ws.columns:
            max_length = 0
            column_letter = column[0].column_letter
            for cell in column:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except:
                    pass
            adjusted_width = (max_length + 2) * 1.2
            ws.column_dimensions[column_letter].width = adjusted_width

        # Отправляем файл
        response = HttpResponse(
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        response["Content-Disposition"] = (
            f'attachment; filename="Участники_{event.title}.xlsx"'
        )

        wb.save(response)
        return response

    elif export_format == "pdf":
        # Создаем PDF-файл
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import letter
        from reportlab.lib import colors
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        import os

        # Регистрируем шрифт DejaVuSans для поддержки кириллицы
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        font_path = os.path.join(base_dir, "DejaVuSans.ttf")
        pdfmetrics.registerFont(TTFont("DejaVuSans", font_path))

        font_bold_path = os.path.join(base_dir, "DejaVuSans-Bold.ttf")
        pdfmetrics.registerFont(TTFont("DejaVuSans-Bold", font_bold_path))

        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter)
        elements = []

        # Стили
        styles = getSampleStyleSheet()
        styles["Title"].fontName = "DejaVuSans-Bold"
        styles["Normal"].fontName = "DejaVuSans"

        # Заголовок
        elements.append(Paragraph(f"Список участников: {event.title}", styles["Title"]))

        # Данные для таблицы
        data = [
            [
                "Имя",
                "E-mail",
                "Телефон",
                "Дата покупки",
                "Тип билета",
                "Статус",
                "Цена",
            ]
        ]

        for index, order in enumerate(orders, 1):
            data.append(
                [
                    f"{order.participant_data.get('first_name', '')} {order.participant_data.get('last_name', '')}".strip(),
                    order.participant_data.get("email", ""),
                    order.participant_data.get("phone", ""),
                    order.created_at.strftime("%d.%m.%Y %H:%M"),
                    order.ticket.name,
                    "Оплачено" if order.attended else "Ожидает оплаты",
                    f"{order.total_price:.2f} руб.",
                ]
            )

        # Создаем таблицу
        table = Table(data)
        # Устанавливаем ширину столбцов (в порядке: №, Имя, E-mail, Дата покупки, Тип билета, Количество, Стоимость, Статус посещения)
        column_widths = [80, 110, 100, 80, 70, 70, 80]
        table._argW = column_widths

        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("FONTNAME", (0, 0), (-1, 0), "DejaVuSans-Bold"),
                    (
                        "FONTSIZE",
                        (0, 0),
                        (-1, 0),
                        8,
                    ),  # Увеличен размер шрифта для заголовка
                    ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
                    ("BACKGROUND", (0, 1), (-1, -1), colors.beige),
                    ("GRID", (0, 0), (-1, -1), 1, colors.black),
                    ("FONTNAME", (0, 1), (-1, -1), "DejaVuSans"),
                    (
                        "FONTSIZE",
                        (0, 1),
                        (-1, -1),
                        6,
                    ),  # Увеличен размер шрифта для данных
                ]
            )
        )

        elements.append(table)
        doc.build(elements)

        # Отправляем файл
        buffer.seek(0)
        response = HttpResponse(buffer, content_type="application/pdf")
        response["Content-Disposition"] = (
            f'attachment; filename="Участники_{event.title}.pdf"'
        )
        return response

    return HttpResponse("Неверный формат экспорта", status=400)


@login_required
def mark_attendance(request, event_id, order_id):
    """
    Отмечает участника как посетившего мероприятие.
    """
    # Получаем мероприятие или выдаем 404, если его нет или оно чужое
    event = get_object_or_404(Event, id=event_id, organizer=request.user)

    # Получаем заказ
    order = get_object_or_404(Order, id=order_id, ticket__event=event)

    if request.method == "POST":
        # Инвертируем статус посещения
        order.attended = not order.attended
        order.save()
        messages.success(
            request,
            f"Статус посещения для {order.participant_data.get('name', 'участника')} обновлен!",
        )

    return redirect("partner:participant_list", event_id=event.id)


@login_required
def check_ticket(request, order_id):
    """
    Проверка билета по QR-коду.
    """
    order = get_object_or_404(Order, id=order_id)

    context = {
        "order": order,
        "is_valid": True,
    }
    return render(request, "partner/ticket_check.html", context)


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
        send_email = request.POST.get("send_email", "false").lower() == "true"

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
                    ContentFile(report_file.read()),
                )
            elif report_type == "excel":
                file_name = f"report_{period_start}_{period_end}.xlsx"
                report.file_path.save(
                    file_name,
                    ContentFile(report_file.getvalue()),
                )
            else:
                file_name = f"report_{period_start}_{period_end}.pdf"
                report.file_path.save(
                    file_name,
                    ContentFile(report_file.getvalue()),
                )

            # Если нужно отправить на email
            if send_email:
                email = EmailMessage(
                    subject=f"Отчёт о продажах с {period_start} по {period_end}",
                    body=f"Добрый день!\n\nПрикрепляем отчёт о продажах за период с {period_start} по {period_end}.\n\nС уважением, ваша платформа мероприятий.",
                    from_email=None,
                    to=[request.user.email],
                )
                email.attach(
                    file_name, report_file.getvalue(), f"application/{report_type}"
                )
                email.send()

            # Возвращаем ссылку на скачивание
            return JsonResponse(
                {
                    "status": "success",
                    "download_url": report.file_path.url,
                    "email_sent": send_email,
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


@login_required
def report_schedule(request):
    """
    Настройка расписания отправки отчётов.
    """
    try:
        # Получаем или создаём настройки расписания для текущего пользователя
        schedule, created = ReportSchedule.objects.get_or_create(partner=request.user)

        if request.method == "POST":
            form = ReportScheduleForm(
                request.POST, instance=schedule, partner=request.user
            )
            if form.is_valid():
                form.save()
                messages.success(request, "Настройки расписания успешно сохранены!")
                return redirect("partner:report_schedule")
            else:
                messages.error(request, "Пожалуйста, исправьте ошибки в форме.")
        else:
            form = ReportScheduleForm(instance=schedule, partner=request.user)

        return render(request, "partner/report_schedule.html", {"form": form})
    except Exception as e:
        import logging

        logger = logging.getLogger(__name__)
        logger.exception("Ошибка в представлении report_schedule: %s", str(e))
        messages.error(request, f"Произошла ошибка: {str(e)}")
        return redirect("partner:dashboard")
