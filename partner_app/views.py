from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.core.files.base import ContentFile
from django.core.mail import send_mail, EmailMessage
from django.utils import timezone
from django.db.models import Sum, Count, Avg, F, ExpressionWrapper, DecimalField
from django.db.models.functions import TruncDate
from django.contrib import messages
from django.shortcuts import redirect
import logging
from django.contrib.auth import update_session_auth_hash
from datetime import datetime, timedelta
import os
import json
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from django.db import transaction
from django.core.exceptions import ObjectDoesNotExist
from core.models import Event, Ticket, Order, PayoutRequest, PayoutDetails, Tag
from .forms import EventForm, DocumentUploadForm, ReportScheduleForm, PayoutDetailsForm
from .models import SalesReport, ReportSchedule
from .utils import generate_sales_report
from core.forms import PartnerProfileForm, PasswordChangeForm

logger = logging.getLogger(__name__)


def get_rejection_messages(request):
    """Возвращает сообщения об отклонении мероприятий для текущего пользователя."""
    from core.models import Event

    rejected_events = Event.objects.filter(organizer=request.user, status="rejected")

    rejection_messages = []
    for event in rejected_events:
        if event.rejection_reason:
            rejection_messages.append(
                f"Мероприятие {event.title} отклонено. Причина: {event.rejection_reason}"
            )

    return rejection_messages


@login_required
def partner_dashboard(request):
    if request.user.user_type != "partner":
        return redirect("visitor:dashboard")

    # Получаем отклоненные мероприятия партнёра
    rejected_events = Event.objects.filter(organizer=request.user, status="rejected")

    rejection_messages = []
    for event in rejected_events:
        if event.rejection_reason:
            rejection_messages.append(
                f"Мероприятие '{event.title}' отклонено. Причина: {event.rejection_reason}"
            )

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
        "rejection_messages": rejection_messages,
    }
    return render(request, "partner/dashboard.html", context)


@login_required
def create_event(request):
    """
    View для создания нового мероприятия.
    Видео обрабатывается автоматически через сигналы и Celery.
    """
    if request.method == "POST":
        form = EventForm(request.POST, request.FILES)
        if form.is_valid():
            event = form.save(commit=False)
            event.organizer = request.user
            event.status = "on_moderation"

            # Очищаем медиафайлы, если были отмечены соответствующие флаги
            for field_name in ["image", "video_url", "program_file"]:
                clear_field_name = f"{field_name}-clear"
                if clear_field_name in request.POST:
                    current_file = getattr(event, field_name)
                    if current_file:
                        current_file.delete(save=False)  # Не сохраняем модель здесь
                    setattr(event, field_name, None)

        event.save()

        # Обрабатываем теги из массива ID
        tags_ids = request.POST.getlist("tags")
        if tags_ids:
            # Ограничиваем количество тегов до 5
            selected_tags = tags_ids[:5]
            event.tags.set(selected_tags)

        # Обрабатываем данные о билетах из таблицы
        ticket_names = request.POST.getlist("ticket_name[]")
        ticket_prices = request.POST.getlist("ticket_price[]")
        ticket_quantities = request.POST.getlist("ticket_quantity[]")

        for name, price, quantity in zip(
            ticket_names, ticket_prices, ticket_quantities
        ):
            if name and price and quantity:
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

        # РЕДИРЕКТИМ пользователя.
        # Обработка видео начнется автоматически через сигнал post_save.
        messages.success(
            request,
            "Мероприятие успешно создано! Видео будет обработано в фоновом режиме.",
        )
        return redirect("partner:partner_event_list")
    else:
        form = EventForm()

    ticket_data = []
    if request.method == "POST" and not form.is_valid():
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
            "rejection_messages": get_rejection_messages(request),
            "all_tags": Tag.objects.all(),
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
    Видео обрабатывается автоматически при замене файла.
    """
    event = get_object_or_404(Event, id=event_id, organizer=request.user)

    if event.has_sold_tickets:
        messages.error(
            request,
            "Редактирование этого мероприятия запрещено, так как на него уже проданы билеты.",
        )
        return redirect("partner:partner_event_list")

    if request.method == "POST":
        # Передаем request.FILES, чтобы обработать загрузку нового видео
        form = EventForm(request.POST, request.FILES, instance=event)

        # --- НАЧАЛО БЛОГА ИЗМЕНЕНИЙ ---
        # Эта логика удаляет старое видео с диска, если был загружен новый файл.
        # Она должна выполняться ДО валидации и сохранения формы.

        # Проверяем, был ли загружен НОВЫЙ файл для поля 'video_url'
        new_video_file = request.FILES.get("video_url")

        # Если новый файл есть, и у события уже было старое видео...
        if new_video_file and event.video_url:
            # ...то удаляем старый файл с диска.
            # Метод .delete() у FileField удаляет файл с диска.
            # Параметр save=False важен: мы не хотим сохранять модель сейчас.
            event.video_url.delete(save=False)

        # --- КОНЕЦ БЛОГА ИЗМЕНЕНИЙ ---

        # Очищаем медиафайлы (изображение, программа), если были отмечены флажки в форме
        for field_name in ["image", "program_file"]:
            clear_field_name = f"{field_name}-clear"
            if clear_field_name in request.POST:
                current_file = getattr(event, field_name)
                if current_file:
                    current_file.delete(save=False)
                setattr(event, field_name, None)

        # Флаг 'video_changed' больше не нужен, так как мы удалили старый файл напрямую

        if form.is_valid():
            # Сохраняем форму. Это обновит путь к видео в БД на новый (если он был загружен).
            event = form.save()

            # Обрабатываем теги из массива ID
            tags_ids = request.POST.getlist("tags")
            if tags_ids:
                # Ограничиваем количество тегов до 5
                selected_tags = tags_ids[:5]
                event.tags.set(selected_tags)

            # Обработка данных о билетах: удаляем старые и создаем новые
            event.tickets.all().delete()
            ticket_names = request.POST.getlist("ticket_name[]")
            ticket_prices = request.POST.getlist("ticket_price[]")
            ticket_quantities = request.POST.getlist("ticket_quantity[]")

            for name, price, quantity in zip(
                ticket_names, ticket_prices, ticket_quantities
            ):
                if name and price and quantity:
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
        form = EventForm(instance=event)

    return render(
        request,
        "partner/event_form.html",
        {
            "form": form,
            "is_edit": True,
            "rejection_messages": get_rejection_messages(request),
            "all_tags": Tag.objects.all(),
        },
    )


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
        "rejection_messages": get_rejection_messages(request),
    }
    return render(request, "partner/partner_event_list.html", context)


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

    # Расчет общей статистики (без учёта возвратов)
    non_refunded_orders = orders.exclude(payment_status__in=["canceled", "refunded"])
    total_sales = non_refunded_orders.aggregate(total=Sum("total_price"))["total"] or 0

    # Считаем количество возвратов
    refunded_orders = orders.filter(payment_status__in=["canceled", "refunded"])
    total_refunds = refunded_orders.aggregate(total=Sum("total_price"))["total"] or 0

    # Считаем реальное количество проданных билетов (без возвратов)
    tickets_sold = sum(order.quantity for order in non_refunded_orders)

    # Средний чек = общая выручка / количество проданных билетов
    avg_check = total_sales / tickets_sold if tickets_sold > 0 else 0

    # Получаем данные для графика продаж по дням (без учёта возвратов)
    sales_graph_data = (
        non_refunded_orders.annotate(date=TruncDate("created_at"))
        .values("date")
        .annotate(total=Sum("total_price"))
        .order_by("date")
    )

    # Преобразуем в формат для Chart.js (конвертируем Decimal в float)
    sales_graph_data = {
        item["date"].strftime("%Y-%m-%d"): float(item["total"])
        for item in sales_graph_data
    }

    # Получаем данные об источниках трафика (без учёта возвратов)
    traffic_sources = (
        non_refunded_orders.exclude(utm_source__isnull=True)
        .exclude(utm_source__exact="")
        .values("utm_source")
        .annotate(total=Sum("total_price"), count=Count("id"))
        .order_by("-total")
    )

    # Преобразуем в удобный формат
    traffic_sources_data = {
        item["utm_source"]: {"total": float(item["total"]), "count": item["count"]}
        for item in traffic_sources
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
        "total_refunds": "{:,.2f}".format(total_refunds).replace(",", " "),
        "refunded_tickets": sum(order.quantity for order in refunded_orders),
        "sales_graph_data": json.dumps(sales_graph_data),
        "traffic_sources_data": traffic_sources_data,
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

    # Базовый фильтр: только заказы для этого мероприятия, исключая возвраты
    orders = (
        Order.objects.filter(ticket__event=event)
        .exclude(payment_status__in=["canceled", "refunded"])
        .select_related("ticket")
    )

    # Применяем фильтры
    if search_name:
        orders = orders.filter(participant_data__name__icontains=search_name)
    if search_email:
        orders = orders.filter(participant_data__email__icontains=search_email)
    if search_status == "is_paid":
        orders = orders.filter(is_paid=True)
    elif search_status == "not_paid":
        orders = orders.filter(is_paid=False)

    # Обработка экспорта
    export_format = request.GET.get("export")
    if export_format:
        # Для экспорта также исключаем возвраты
        export_orders = orders.exclude(payment_status__in=["canceled", "refunded"])
        return export_participant_list(export_orders, event, export_format)

    context = {
        "event": event,
        "orders": orders,
    }
    context["rejection_messages"] = get_rejection_messages(request)
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
            "Количество билетов",
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
                value="Оплачено" if order.is_paid else "Не оплачен",
            )
            ws.cell(row=row_num, column=7, value=f"{order.total_price:.2f} руб.")
            ws.cell(
                row=row_num, column=8, value=f"Количество билетов: {order.quantity}"
            )

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
        from reportlab.platypus import (
            SimpleDocTemplate,
            Table,
            TableStyle,
            Paragraph,
            Image,
        )
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        import os
        import qrcode
        import io

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
                "Кол-во",
                "QR",
            ]
        ]

        for index, order in enumerate(orders, 1):
            # Генерация QR-кодов
            qr_images = []
            for i in range(order.quantity):
                qr = qrcode.QRCode(
                    version=1,
                    error_correction=qrcode.constants.ERROR_CORRECT_L,
                    box_size=10,
                    border=4,
                )
                qr.add_data(f"Order ID: {order.id}, Билет: {i+1}")
                qr.make(fit=True)
                img = qr.make_image(fill_color="black", back_color="white")
                qr_code_img = io.BytesIO()
                img.save(qr_code_img, format="PNG")
                qr_code_img.seek(0)
                qr_images.append(Image(qr_code_img, width=40, height=40))

            # Для первой строки заказа добавляем QR-коды в таблицу
            if qr_images:
                qr_cell = qr_images[0]  # Первый QR-код в основной строке
                other_qrs = qr_images[
                    1:
                ]  # Остальные QR-коды добавим как дополнительные строки
            else:
                qr_cell = " "
                other_qrs = []

            data.append(
                [
                    f"{order.participant_data.get('first_name', '')} {order.participant_data.get('last_name', '')}".strip(),
                    order.participant_data.get("email", ""),
                    order.participant_data.get("phone", ""),
                    order.created_at.strftime("%d.%m.%Y %H:%M"),
                    order.ticket.name,
                    "Оплачено" if order.is_paid else "Не оплачен",
                    f"{order.total_price:.2f} руб.",
                    f"{order.quantity}",
                    qr_cell,
                ]
            )

            # Добавляем дополнительные QR-коды как отдельные строки в таблицу
            for qr_img in other_qrs:
                data.append(["", "", "", "", "", "", "", "", qr_img])

        # Создаем таблицу
        table = Table(data)
        # Устанавливаем ширину столбцов
        column_widths = [80, 100, 60, 70, 70, 60, 60, 40, 50]
        table._argW = column_widths

        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                    ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                    ("FONTNAME", (0, 0), (-1, 0), "DejaVuSans-Bold"),
                    ("FONTSIZE", (0, 0), (-1, 0), 8),
                    ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
                    ("BACKGROUND", (0, 1), (-1, -1), colors.beige),
                    ("GRID", (0, 0), (-1, -1), 1, colors.black),
                    ("FONTNAME", (0, 1), (-1, -1), "DejaVuSans"),
                    ("FONTSIZE", (0, 1), (-1, -1), 6),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("WORDWRAP", (0, 0), (-1, -1), True),
                    ("LEFTPADDING", (0, 0), (-1, -1), 5),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                    ("ALIGN", (7, 0), (7, -1), "CENTER"),
                ]
            )
        )

        elements.append(table)
        doc.build(elements)

        # Отправляем файл
        buffer.seek(0)
        response = HttpResponse(buffer, content_type="application/pdf")
        response["Content-Disposition"] = (
            f'attachment; filename="Участники_{event.title}_с_QR.pdf"'
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

    # Считаем общую выручку (только оплаченные заказы, кроме возвратов)
    total_revenue = (
        orders.filter(is_paid=True)
        .exclude(payment_status="refunded")
        .aggregate(total=Sum("total_price"))["total"]
        or 0
    )

    commission_sum = (
        orders.filter(is_paid=True)
        .exclude(payment_status="refunded")
        .annotate(
            event_commission=ExpressionWrapper(
                F("total_price") * (F("ticket__event__commission_rate") / 100),
                output_field=DecimalField(),
            )
        )
        .aggregate(total_commission=Sum("event_commission"))["total_commission"]
        or 0
    )
    commission_amount = commission_sum
    # Сумма к выплате: выручка минус комиссия
    payout_amount = total_revenue - commission_sum

    payout_history = PayoutRequest.objects.filter(organizer=request.user).order_by(
        "-created_at"
    )

    # Получаем реквизиты партнёра
    partner_payout_details = PayoutDetails.objects.filter(partner=request.user)

    context = {
        "total_revenue": total_revenue,
        "commission_amount": commission_amount,
        "payout_amount": payout_amount,
        "payout_history": payout_history,
        "partner_payout_details": partner_payout_details,
    }
    context["rejection_messages"] = get_rejection_messages(request)
    return render(request, "partner/finances.html", context)


@require_POST
@csrf_exempt
def request_payout(request):
    """
    Обработка AJAX-запроса на создание запроса выплаты.
    """
    try:
        data = request.POST
        amount = float(data.get("amount", 0))
        payout_details_id = data.get("payout_details")
        comment = data.get("comment", "")

        if not payout_details_id:
            return JsonResponse(
                {
                    "status": "error",
                    "message": "Пожалуйста, выберите реквизиты для выплаты",
                },
                status=400,
            )

        try:
            payout_details = PayoutDetails.objects.get(
                id=payout_details_id, partner=request.user
            )
        except ObjectDoesNotExist:
            return JsonResponse(
                {"status": "error", "message": "Выбранные реквизиты не найдены"},
                status=404,
            )

        # Получаем доступную для выплаты сумму (только оплаченные заказы, кроме возвратов)
        orders = Order.objects.filter(ticket__event__organizer=request.user)
        total_revenue = (
            orders.filter(is_paid=True)
            .exclude(payment_status="refunded")
            .aggregate(total=Sum("total_price"))["total"]
            or 0
        )
        commission_sum = (
            orders.filter(is_paid=True)
            .exclude(payment_status="refunded")
            .annotate(
                event_commission=ExpressionWrapper(
                    F("total_price") * (F("ticket__event__commission_rate") / 100),
                    output_field=DecimalField(),
                )
            )
            .aggregate(total_commission=Sum("event_commission"))["total_commission"]
            or 0
        )
        payout_amount = total_revenue - commission_sum

        # Серверная валидация суммы выплаты
        if amount > payout_amount:
            return JsonResponse(
                {
                    "status": "error",
                    "message": f"Сумма выплаты не может превышать доступную сумму: {payout_amount:.2f} ₽",
                },
                status=400,
            )

        # Создаём запрос на выплату
        payout_request = PayoutRequest.objects.create(
            organizer=request.user,
            amount=amount,
            payment_details=payout_details,
            comment=comment,
            status="pending",
        )

        return JsonResponse(
            {"status": "success", "message": "Запрос на выплату успешно создан!"}
        )

    except Exception as e:
        return JsonResponse(
            {"status": "error", "message": f"Произошла ошибка: {str(e)}"}, status=500
        )


@require_POST
@login_required
def cancel_payout(request, payout_id):
    """
    Отмена заявки на выплату через AJAX.
    """
    try:
        # Ищем заявку, которая принадлежит текущему пользователю
        payout_request = get_object_or_404(
            PayoutRequest, id=payout_id, organizer=request.user
        )

        # Проверяем, можно ли отменить (статус должен быть 'pending')
        if payout_request.status != "pending":
            return JsonResponse(
                {
                    "status": "error",
                    "message": 'Отменить можно только заявку в статусе "Ожидает обработки"',
                },
                status=400,
            )

        # Меняем статус и сохраняем
        payout_request.status = "cancelled"
        payout_request.save()

        return JsonResponse(
            {"status": "success", "message": "Заявка на выплату отменена!"}
        )

    except Exception as e:
        return JsonResponse(
            {"status": "error", "message": f"Произошла ошибка: {str(e)}"}, status=500
        )


@require_POST
@csrf_exempt
def delete_reports(request):
    """
    Удаление выбранных отчётов через AJAX.
    """
    try:
        data = json.loads(request.body)
        report_ids = data.get("report_ids", [])

        if not report_ids:
            return JsonResponse(
                {
                    "status": "error",
                    "message": "Не выбрано ни одного отчёта для удаления",
                },
                status=400,
            )

        # Удаляем отчёты и их файлы
        deleted_count = 0
        for report_id in report_ids:
            try:
                report = SalesReport.objects.get(id=report_id, partner=request.user)
                if report.file_path:
                    report.file_path.delete()
                report.delete()
                deleted_count += 1
            except ObjectDoesNotExist:
                continue

        return JsonResponse(
            {
                "status": "success",
                "message": f"Успешно удалено {deleted_count} отчёт(ов)",
            }
        )

    except Exception as e:
        return JsonResponse(
            {"status": "error", "message": f"Произошла ошибка: {str(e)}"}, status=500
        )


@login_required
def payout_details(request):
    """
    Страница для добавления и просмотра реквизитов для выплат.
    """
    # Получаем все реквизиты текущего пользователя
    details = PayoutDetails.objects.filter(partner=request.user)

    if request.method == "POST":
        form = PayoutDetailsForm(request.POST)
        if form.is_valid():
            payout_detail = form.save(commit=False)
            payout_detail.partner = request.user
            payout_detail.save()
            messages.success(request, "Реквизиты успешно сохранены!")
            return redirect("partner:payout_details")
    else:
        form = PayoutDetailsForm()

    context = {
        "form": form,
        "details": details,
        "rejection_messages": get_rejection_messages(request),
    }
    return render(request, "partner/payout_details.html", context)


@login_required
def profile_edit(request):
    """
    View для редактирования профиля партнера.
    Включает обработку видео-визитки.
    """
    if request.method == "POST":
        # Инициализируем форму с данными и файлами
        user_form = PartnerProfileForm(
            request.POST, request.FILES, instance=request.user
        )

        # --- НАЧАЛО БЛОКА ИЗМЕНЕНИЙ ---
        # Эта логика удаляет старое видео-визитку с диска, если был загружен новый файл.
        # Она должна выполняться ДО валидации и сохранения формы.

        # Проверяем, был ли загружен НОВЫЙ файл для поля 'video_business_card'
        new_video_file = request.FILES.get("video_business_card")

        # Если новый файл есть, и у пользователя уже было старое видео...
        if new_video_file and request.user.video_business_card:
            # ...то удаляем старый файл с диска.
            # Метод .delete() у FileField удаляет файл с диска.
            # Параметр save=False важен: мы не хотим сохранять модель сейчас.
            request.user.video_business_card.delete(save=False)
        # --- КОНЕЦ БЛОКА ИЗМЕНЕНИЙ ---

        # Обработка основной формы профиля (включая видео-визитку)
        if user_form.is_valid():
            user_form.save()  # Сохранение здесь запустит сигнал для обработки нового видео

        # Обработка формы смены пароля
        password_form = PasswordChangeForm(user=request.user, data=request.POST)
        if password_form.is_valid():
            password_form.save()
            update_session_auth_hash(request, password_form.user)

        # Обработка формы загрузки документов
        if "upload_documents" in request.POST:
            if request.user.verification_status == "not_submitted":
                document_form = DocumentUploadForm(
                    request.POST, request.FILES, user=request.user
                )
                if document_form.is_valid():
                    document_form.save()
                    request.user.verification_status = "pending"
                    request.user.save()

        messages.success(request, "Ваши изменения успешно сохранены!")
        return redirect("partner:dashboard")

    else:
        user_form = PartnerProfileForm(instance=request.user)
        password_form = PasswordChangeForm(user=request.user)
        document_form = DocumentUploadForm(user=request.user)

    context = {
        "user_form": user_form,
        "password_form": password_form,
        "document_form": document_form,
        "rejection_messages": get_rejection_messages(request),
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

        return render(
            request,
            "partner/report_schedule.html",
            {"form": form, "rejection_messages": get_rejection_messages(request)},
        )
    except Exception as e:
        import logging

        logger = logging.getLogger(__name__)
        logger.exception("Ошибка в представлении report_schedule: %s", str(e))
        messages.error(request, f"Произошла ошибка: {str(e)}")
        return redirect("partner:dashboard")


@login_required
def remove_media(request, media_type, media_id):
    """
    View для удаления медиафайлов через AJAX.
    """
    if request.method != "POST":
        return JsonResponse(
            {"status": "error", "message": "Method not allowed"}, status=405
        )

    try:
        if media_type == "image":
            event = Event.objects.get(id=media_id, organizer=request.user)
            if event.image:
                event.image.delete(save=False)
                event.image = None
                event.save()
                return JsonResponse({"status": "success"})

        elif media_type == "video_url":
            event = Event.objects.get(id=media_id, organizer=request.user)
            if event.video_url:
                event.video_url.delete(save=False)
                event.video_url = None
                event.save()
                return JsonResponse({"status": "success"})

        elif media_type == "program_file":
            event = Event.objects.get(id=media_id, organizer=request.user)
            if event.program_file:
                event.program_file.delete(save=False)
                event.program_file = None
                event.save()
                return JsonResponse({"status": "success"})

        elif media_type == "video_business_card":
            if request.user.video_business_card:
                request.user.video_business_card.delete(save=False)
                request.user.video_business_card = None
                request.user.save()
                return JsonResponse({"status": "success"})

        return JsonResponse(
            {"status": "error", "message": "Media not found"}, status=404
        )

    except Exception as e:
        return JsonResponse({"status": "error", "message": str(e)}, status=500)


@login_required
def change_password(request):
    """Отдельная страница для смены пароля в личном кабинете партнёра."""
    if request.method == "POST":
        password_form = PasswordChangeForm(user=request.user, data=request.POST)
        if password_form.is_valid():
            password_form.save()
            update_session_auth_hash(request, password_form.user)
            messages.success(request, "Пароль успешно изменён!")
            return redirect("partner:dashboard")
    else:
        password_form = PasswordChangeForm(user=request.user)

    return render(
        request,
        "change_password.html",
        {"form": password_form, "rejection_messages": get_rejection_messages(request)},
    )
