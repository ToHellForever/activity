import csv
import io
from datetime import datetime
from django.http import HttpResponse
from openpyxl import Workbook
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from core.models import Order, Ticket, Event


def generate_sales_report(partner, period_start, period_end, report_type):
    """
    Генерирует отчёт о продажах в указанном формате.
    """
    # Получаем заказы партнёра за указанный период
    orders = Order.objects.filter(
        ticket__event__organizer=partner,
        created_at__date__range=[period_start, period_end],
    ).select_related("ticket__event")

    # Подготавливаем данные для отчёта
    report_data = []
    total_sales = 0
    total_tickets = 0

    for order in orders:
        event_title = order.ticket.event.title
        ticket_name = order.ticket.name
        quantity = order.quantity
        total_price = order.total_price
        order_date = order.created_at.strftime("%d.%m.%Y %H:%M")

        report_data.append(
            {
                "event": event_title,
                "ticket": ticket_name,
                "quantity": quantity,
                "price": total_price,
                "date": order_date,
            }
        )

        total_sales += total_price
        total_tickets += quantity

    # Добавляем итоговую строку
    report_data.append(
        {
            "event": "ИТОГО:",
            "ticket": "",
            "quantity": total_tickets,
            "price": total_sales,
            "date": "",
        }
    )

    # Генерируем отчёт в зависимости от типа
    if report_type == "csv":
        return generate_csv_report(report_data, period_start, period_end)
    elif report_type == "excel":
        return generate_excel_report(report_data, period_start, period_end)
    elif report_type == "pdf":
        return generate_pdf_report(report_data, period_start, period_end)
    else:
        raise ValueError("Неверный формат отчёта")


def generate_csv_report(data, period_start, period_end):
    """Генерирует отчёт в формате CSV с поддержкой кириллицы."""
    output = io.StringIO(newline="")
    # Используем UTF-8 с BOM для корректного отображения в Excel
    output.write("\ufeff")
    writer = csv.writer(output, quoting=csv.QUOTE_MINIMAL)

    # Заголовки
    writer.writerow(
        ["Мероприятие", "Тип билета", "Количество", "Сумма (₽)", "Дата заказа"]
    )

    # Данные
    for row in data:
        writer.writerow(
            [
                row["event"],
                row["ticket"],
                row["quantity"],
                row["price"],
                row["date"],
            ]
        )

    content = output.getvalue()
    output.close()
    return io.BytesIO(content.encode("utf-8-sig"))


def generate_excel_report(data, period_start, period_end):
    """Генерирует отчёт в формате Excel с поддержкой кириллицы."""
    wb = Workbook()
    ws = wb.active
    ws.title = f"Отчёт с {period_start} по {period_end}"

    # Заголовки
    ws.append(["Мероприятие", "Тип билета", "Количество", "Сумма (₽)", "Дата заказа"])

    # Данные
    for row in data:
        ws.append(
            [
                row["event"],
                row["ticket"],
                row["quantity"],
                row["price"],
                row["date"],
            ]
        )

    # Авторазмер колонок
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

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return output


def generate_pdf_report(data, period_start, period_end):
    """Генерирует отчёт в формате PDF с поддержкой кириллицы."""
    # Регистрируем шрифт с поддержкой кириллицы
    pdfmetrics.registerFont(TTFont("DejaVuSans", "DejaVuSans.ttf"))
    pdfmetrics.registerFont(TTFont("DejaVuSans-Bold", "DejaVuSans-Bold.ttf"))

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=30,
        leftMargin=30,
        topMargin=30,
        bottomMargin=18,
    )

    styles = getSampleStyleSheet()
    # Обновляем стили для поддержки кириллицы
    styles["Title"].fontName = "DejaVuSans-Bold"
    styles["Normal"].fontName = "DejaVuSans"
    elements = []

    # Заголовок
    title = Paragraph(
        f"Отчёт о продажах с {period_start.strftime('%d.%m.%Y')} по {period_end.strftime('%d.%m.%Y')}",
        styles["Title"],
    )
    elements.append(title)
    elements.append(Paragraph("<br/><br/>", styles["Normal"]))

    # Таблица с данными
    table_data = [
        ["Мероприятие", "Тип билета", "Количество", "Сумма (₽)", "Дата заказа"]
    ]

    for row in data:
        table_data.append(
            [
                row["event"],
                row["ticket"],
                str(row["quantity"]),
                f"{row['price']:.2f}",
                row["date"],
            ]
        )

    table = Table(table_data)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                ("FONTNAME", (0, 0), (-1, 0), "DejaVuSans-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 12),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
                ("BACKGROUND", (0, 1), (-1, -1), colors.beige),
                ("GRID", (0, 0), (-1, -1), 1, colors.black),
                ("FONTNAME", (0, 1), (-1, -1), "DejaVuSans"),
            ]
        )
    )

    elements.append(table)
    doc.build(elements)

    buffer.seek(0)
    return buffer
