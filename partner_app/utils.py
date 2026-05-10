import csv
import io
import qrcode
from datetime import datetime
from django.http import HttpResponse
from openpyxl import Workbook
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Image
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
            "is_total": True,  # Флаг для итоговой строки
        }
    )

    # Генерируем отчёт в зависимости от типа
    if report_type == "csv":
        return generate_csv_report(report_data, period_start, period_end)
    elif report_type == "excel":
        return generate_excel_report(report_data, period_start, period_end)
    elif report_type == "pdf":
        return generate_pdf_report(report_data, period_start, period_end, orders=orders)
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
        if row.get("is_total"):
            # Итоговая строка
            ws.append(
                [
                    row.get("event", row.get("name", "")),
                    row.get("ticket", ""),
                    row.get("quantity", ""),
                    row.get("price", 0),
                    row.get("date", ""),
                ]
            )
        else:
            # Обычная строка
            ws.append(
                [
                    row.get("event", row.get("name", "")),
                    row.get("ticket", ""),
                    row.get("quantity", ""),
                    row.get("price", 0),
                    row.get("date", ""),
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


def generate_qr_code(order_id):
    """
    Генерирует QR-код для заказа и возвращает его в виде изображения.
    """
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(f"Order ID: {order_id}")
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")
    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format='PNG')
    img_byte_arr.seek(0)
    return img_byte_arr

def generate_pdf_report(data, period_start, period_end, orders=None):
    """Генерирует отчёт в формате PDF с поддержкой кириллицы и QR-кодами."""
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
        ["Мероприятие", "Тип билета", "Кол-во", "Сумма (₽)", "Дата заказа"]
    ]

    for idx, row in enumerate(data):
        if row.get("is_total"):
            # Итоговая строка
            table_data.append(
                [
                    row.get("event", row.get("name", "")),
                    row.get("ticket", ""),
                    str(row.get("quantity", "")),
                    f"{row.get('price', 0):.2f}",
                    row.get("date", ""),
                ]
            )
        else:
            # Обычная строка
            table_data.append(
                [
                    row.get("event", row.get("name", "")),
                    row.get("ticket", ""),
                    str(row.get("quantity", "")),
                    f"{row.get('price', 0):.2f}",
                    row.get("date", ""),
                ]
            )

    table = Table(table_data, colWidths=[120, 120, 100, 80, 100])
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
