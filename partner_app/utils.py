import csv
import io
import qrcode
import calendar
from datetime import datetime
from decimal import Decimal
from openpyxl import Workbook
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from django.conf import settings
from core.models import Order, OrderTicket


def generate_sales_report(partner, period_start, period_end, report_type):
    """
    Генерирует отчёт о продажах в указанном формате.
    """
    # Получаем заказы партнёра за указанный период
    orders = Order.objects.filter(
        ticket__event__organizer=partner,
        created_at__date__range=[period_start, period_end],
    ).select_related("ticket__event")

    # Разделяем заказы на обычные и возвраты
    refunded_orders = orders.filter(payment_status__in=["canceled", "refunded"])
    non_refunded_orders = orders.exclude(payment_status__in=["canceled", "refunded"])

    # Подготавливаем данные для отчёта
    report_data = []
    total_sales = 0
    total_tickets = 0
    total_refunds = 0
    total_refunded_tickets = 0

    # Обрабатываем обычные заказы
    for order in non_refunded_orders:
        event_title = order.ticket.event.title
        ticket_name = order.ticket.name
        quantity = order.quantity
        total_price = order.total_price
        order_date = order.created_at.strftime("%d.%m.%Y")

        report_data.append(
            {
                "event": event_title,
                "ticket": ticket_name,
                "quantity": quantity,
                "price": total_price,
                "date": order_date,
                "refund": "-",  # Пометка, что это не возврат
                "status": order.get_payment_status_display(),
            }
        )

        total_sales += total_price
        total_tickets += quantity

    # Обрабатываем возвраты
    for order in refunded_orders:
        event_title = order.ticket.event.title
        ticket_name = order.ticket.name
        quantity = order.quantity
        total_price = order.total_price
        order_date = order.created_at.strftime("%d.%m.%Y")

        report_data.append(
            {
                "event": event_title,
                "ticket": ticket_name,
                "quantity": quantity,
                "price": total_price,
                "date": order_date,
                "refund": "Возврат",  # Пометка, что это возврат
                "status": order.get_payment_status_display(),
            }
        )

        total_refunds += total_price
        total_refunded_tickets += quantity

    # Добавляем итоговую строку (без учёта возвратов)
    report_data.append(
        {
            "event": "ИТОГО (без возвратов)",
            "ticket": "",
            "quantity": total_tickets,
            "price": total_sales,
            "date": "",
            "refund": "-",
            "is_total": True,  # Флаг для итоговой строки
        }
    )

    # Добавляем итоговую строку для возвратов
    if total_refunded_tickets > 0:
        report_data.append(
            {
                "event": "ВОЗВРАТЫ:",
                "ticket": "",
                "quantity": total_refunded_tickets,
                "price": total_refunds,
                "date": "",
                "refund": "Возврат",
                "is_refund_total": True,  
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
        [
            "Мероприятие",
            "Тип билета",
            "Количество",
            "Сумма",
            "Дата заказа",
            "Статус",
        ]
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
                row.get("refund", "-"),
            ]
        )

    content = output.getvalue()
    output.close()
    return io.BytesIO(content.encode("utf-8-sig"))


def generate_excel_report(data, period_start, period_end):
    """Генерирует отчёт в формате Excel с поддержкой кириллицы."""
    wb = Workbook()
    ws = wb.active
    # Excel ограничивает имя листа 31 символом
    ws.title = f"Отчёт {period_start:%d.%m.%Y}-{period_end:%d.%m.%Y}"[:31]

    # Заголовки
    ws.append(
        [
            "Мероприятие",
            "Тип билета",
            "Количество",
            "Сумма",
            "Дата заказа",
            "Статус",
        ]
    )

    # Данные
    for row in data:
        if row.get("is_total"):
            # Итоговая строка (без возвратов)
            ws.append(
                [
                    row.get("event", row.get("name", "")),
                    row.get("ticket", ""),
                    row.get("quantity", ""),
                    row.get("price", 0),
                    row.get("date", ""),
                    row.get("refund", "-"),
                ]
            )
        elif row.get("is_refund_total"):
            # Итоговая строка для возвратов
            ws.append(
                [
                    row.get("event", row.get("name", "")),
                    row.get("ticket", ""),
                    row.get("quantity", ""),
                    row.get("price", 0),
                    row.get("date", ""),
                    row.get("refund", "Возврат"),
                ]
            )
        elif row.get("is_net_total"):
            # Итоговая строка для чистой суммы
            ws.append(
                [
                    row.get("event", row.get("name", "")),
                    row.get("ticket", ""),
                    row.get("quantity", ""),
                    row.get("price", 0),
                    row.get("date", ""),
                    row.get("refund", "-"),
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
                    row.get("refund", "-"),
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
    img.save(img_byte_arr, format="PNG")
    img_byte_arr.seek(0)
    return img_byte_arr


def fit_text(text, font_name, font_size, max_width, ellipsis="..."):
    """
    Обрезает строку под ширину колонки: если текст не влезает,
    возвращает его начало с многоточием в конце.
    """
    text = "" if text is None else str(text)
    if pdfmetrics.stringWidth(text, font_name, font_size) <= max_width:
        return text

    while text and pdfmetrics.stringWidth(text + ellipsis, font_name, font_size) > max_width:
        text = text[:-1]
    return text.rstrip() + ellipsis


def format_price(value):
    """Сумма целым числом без копеек (12345.75 -> 12346)."""
    return f"{Decimal(str(value or 0)):,.0f}".replace(",", " ")


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

    # Таблица с данными. Сумма ширин колонок не должна превышать doc.width (552pt)
    col_widths = [130, 120, 55, 65, 90, 100]
    header_font, header_size = "DejaVuSans-Bold", 12
    body_font, body_size = "DejaVuSans", 10
    # reportlab по умолчанию отступает по 6pt слева и справа от текста в ячейке
    inner_widths = [width - 12 for width in col_widths]

    headers = ["Мероприятие", "Тип билета", "Кол-во", "Сумма", "Дата заказа", "Статус"]
    table_data = [
        [
            fit_text(header, header_font, header_size, inner_width)
            for header, inner_width in zip(headers, inner_widths)
        ]
    ]

    for row in data:
        table_data.append(
            [
                fit_text(row.get("event", row.get("name", "")), body_font, body_size, inner_widths[0]),
                fit_text(row.get("ticket", ""), body_font, body_size, inner_widths[1]),
                str(row.get("quantity", "")),
                fit_text(format_price(row.get("price", 0)), body_font, body_size, inner_widths[3]),
                fit_text(row.get("date", ""), body_font, body_size, inner_widths[4]),
                fit_text(row.get("status", ""), body_font, body_size, inner_widths[5]),
            ]
        )

    table = Table(table_data, colWidths=col_widths)
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
                ("FONTNAME", (0, 1), (-1, -1), body_font),
                ("FONTSIZE", (0, 1), (-1, -1), body_size),
            ]
        )
    )

    elements.append(table)
    doc.build(elements)

    buffer.seek(0)
    return buffer


# ============================================================================
# Ежемесячный отчёт агента перед принципалом (организатором)
# ============================================================================

MONTH_NAMES_RU = [
    "январь", "февраль", "март", "апрель", "май", "июнь",
    "июль", "август", "сентябрь", "октябрь", "ноябрь", "декабрь",
]


def _month_bounds(year, month):
    """Первый и последний день месяца."""
    first = datetime(year, month, 1).date()
    last = datetime(year, month, calendar.monthrange(year, month)[1]).date()
    return first, last


def collect_agent_report_data(partner, year, month):
    """
    Собирает данные ежемесячного отчёта агента для принципала (организатора).

    Возвращает словарь:
      - sales_rows: список проданных билетов по категориям
        [{name, quantity, price, total}]
      - refund_rows: список возвратов [{name, quantity, price, total, date}]
      - gross_revenue, refunds_total, net_revenue, agent_fee,
        payable_to_principal — финансовый итог расчёта
      - receipts_count, receipts_total — кассовые чеки за период (54-ФЗ)
    """
    from django.db.models import Sum, Count, Q

    period_start, period_end = _month_bounds(year, month)
    orders = Order.objects.filter(
        ticket__event__organizer=partner,
        created_at__date__range=[period_start, period_end],
        is_paid=True,
    ).select_related("ticket")

    # --- 1. Реализовано билетов (продажи) ---
    # Полностью возвращённые заказы не считаем продажей;
    # поштучно возвращённые билеты исключаем ниже.
    refunded_orders = orders.filter(payment_status__in=["canceled", "refunded"])
    sold_orders = orders.exclude(payment_status__in=["canceled", "refunded"])

    # Поштучно возвращённые билеты в оплаченных (не возвращённых) заказах
    partial_refunds = OrderTicket.objects.filter(
        order__in=sold_orders,
        is_refunded=True,
    ).select_related("order__ticket")

    # quantity по категориям: продано минус поштучные возвраты
    partial_by_ticket = {}
    for ot in partial_refunds:
        partial_by_ticket[ot.order.ticket_id] = (
            partial_by_ticket.get(ot.order.ticket_id, 0) + 1
        )

    sales_rows = []
    sales_agg = (
        sold_orders.values("ticket__id", "ticket__name", "ticket__price")
        .annotate(qty=Sum("quantity"), total=Sum("total_price"))
        .order_by("ticket__name")
    )
    for row in sales_agg:
        qty = row["qty"] - partial_by_ticket.get(row["ticket__id"], 0)
        if qty <= 0:
            continue
        sales_rows.append(
            {
                "name": row["ticket__name"],
                "quantity": qty,
                "price": row["ticket__price"],
                "total": row["ticket__price"] * qty,
            }
        )

    # --- 2. Возвращено билетов (возвраты) ---
    refund_rows = []
    # Полностью возвращённые заказы (дата возврата — дата создания заказа)
    for order in refunded_orders:
        refund_rows.append(
            {
                "name": order.ticket.name,
                "quantity": order.quantity,
                "price": order.ticket.price,
                "total": order.ticket.price * order.quantity,
                "date": order.created_at.strftime("%d.%m.%y"),
            }
        )
    # Поштучные возвраты в оплаченных заказах
    for ot in partial_refunds:
        refund_rows.append(
            {
                "name": ot.order.ticket.name,
                "quantity": 1,
                "price": ot.order.ticket.price,
                "total": ot.order.ticket.price,
                "date": ot.order.created_at.strftime("%d.%m.%y"),
            }
        )

    # --- 3. Финансовый итог расчёта ---
    gross_revenue = sum((r["total"] for r in sales_rows), Decimal("0"))
    refunds_total = sum((r["total"] for r in refund_rows), Decimal("0"))
    net_revenue = gross_revenue - refunds_total
    fee_percent = Decimal(str(settings.AGENT_FEE_PERCENT))
    agent_fee = (net_revenue * fee_percent / Decimal("100")).quantize(Decimal("0.01"))
    payable_to_principal = net_revenue - agent_fee

    # --- 4. Кассовые чеки за период (54-ФЗ) ---
    receipt_orders = orders.exclude(fiscal_receipt_id__isnull=True).exclude(
        fiscal_receipt_id__exact=""
    )
    receipts_count = receipt_orders.count()
    receipts_total = receipt_orders.aggregate(
        total=Sum("total_price")
    )["total"] or Decimal("0")

    return {
        "period_start": period_start,
        "period_end": period_end,
        "sales_rows": sales_rows,
        "refund_rows": refund_rows,
        "gross_revenue": gross_revenue,
        "refunds_total": refunds_total,
        "net_revenue": net_revenue,
        "agent_fee": agent_fee,
        "payable_to_principal": payable_to_principal,
        "receipts_count": receipts_count,
        "receipts_total": receipts_total,
    }


def _principal_requisites(partner, data):
    """
    Реквизиты принципала: из профиля (название организации + ИНН),
    иначе снапшот из заказа, иначе email/ФИО партнёра.
    """
    profile = getattr(partner, "partner_profile", None)
    if profile:
        if profile.company_name:
            kind = {
                "legal": "ООО",
                "ip": "ИП",
                "physical": "Физическое лицо",
                "self_employed": "Самозанятый",
            }.get(profile.registration_type, "")
            name = (
                f"{kind} «{profile.company_name}»"
                if kind and kind not in profile.company_name
                else profile.company_name
            )
        else:
            # Название не заполнено — показываем email партнёра
            name = partner.email
        return name, profile.inn or ""
    # Fallback: снапшот принципала из заказа за период
    order = (
        Order.objects.filter(
            ticket__event__organizer=partner,
            created_at__date__range=[data["period_start"], data["period_end"]],
        )
        .exclude(principal_name__isnull=True)
        .exclude(principal_name__exact="")
        .first()
    )
    if order:
        return order.principal_name, order.principal_inn or ""
    return partner.get_full_name() or partner.username, ""


def generate_agent_report_pdf(partner, year, month, report_number, report_date):
    """
    Генерирует ежемесячный PDF-отчёт агента перед принципалом по ТЗ.

    Структура: шапка (номер/дата/договор/период), реквизиты сторон,
    таблица продаж по категориям, таблица возвратов, финансовый итог,
    уведомление о перечислении и подтверждение по 54-ФЗ.
    """
    pdfmetrics.registerFont(TTFont("DejaVuSans", "DejaVuSans.ttf"))
    pdfmetrics.registerFont(TTFont("DejaVuSans-Bold", "DejaVuSans-Bold.ttf"))

    data = collect_agent_report_data(partner, year, month)
    principal_name, principal_inn = _principal_requisites(partner, data)

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=letter,
        rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=30,
    )

    styles = getSampleStyleSheet()
    styles["Title"].fontName = "DejaVuSans-Bold"
    styles["Normal"].fontName = "DejaVuSans"
    normal = styles["Normal"]
    normal.fontSize = 9
    normal.leading = 13

    def money(value):
        return f"{Decimal(value or 0):,.2f}".replace(",", " ").replace(".", ",")

    def table_style():
        return TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E8E8E8")),
            ("FONTNAME", (0, 0), (-1, 0), "DejaVuSans-Bold"),
            ("FONTNAME", (0, 1), (-1, -1), "DejaVuSans"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("ALIGN", (1, 1), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ])

    elements = []

    # === Шапка документа ===
    # Номер договора: персональный номер партнёра (присваивается при
    # регистрации, с 1), иначе — глобальная настройка, иначе прочерк.
    profile = getattr(partner, "partner_profile", None)
    contract_number = (
        profile.agent_contract_number if profile and profile.agent_contract_number
        else settings.AGENT_CONTRACT_NUMBER or "___"
    )
    month_name = MONTH_NAMES_RU[month - 1]
    elements.append(Paragraph(
        f"Отчёт агента № {report_number} от {report_date.strftime('%d.%m.%Y')} "
        f"по Договору № {contract_number}",
        styles["Title"],
    ))
    elements.append(Paragraph(
        f"Период отчёта: {month_name} {year} г. "
        f"(с {data['period_start'].strftime('%d.%m.%Y')} "
        f"по {data['period_end'].strftime('%d.%m.%Y')})",
        normal,
    ))
    elements.append(Spacer(1, 10))

    # === Реквизиты сторон ===
    agent_line = (
        f"Агент: {settings.AGENT_COMPANY_NAME}"
        + (f" (ИНН {settings.AGENT_INN}" if settings.AGENT_INN else "")
        + (f", ОГРН {settings.AGENT_OGRN})" if settings.AGENT_OGRN else ")"
        if settings.AGENT_INN or settings.AGENT_OGRN else "")
    )
    principal_line = principal_name + (
        f" (ИНН {principal_inn})" if principal_inn else ""
    )
    elements.append(Paragraph(f"{agent_line}", normal))
    elements.append(Paragraph(f"<b>Принципал:</b> {principal_line}", normal))
    elements.append(Spacer(1, 12))

    # === 1. Реализовано билетов (Продажа) ===
    elements.append(Paragraph("<b>1. Реализовано билетов (Продажа)</b>", normal))
    sales_table = [["Наименование билета / Категория", "Кол-во проданных", "Цена за билет,руб.", "Сумма выручки,руб."]]
    for row in data["sales_rows"]:
        sales_table.append([
            row["name"], str(row["quantity"]),
            money(row["price"]), money(row["total"]),
        ])
    sold_total_qty = sum(r["quantity"] for r in data["sales_rows"])
    sales_table.append([
        "Итого проданных билетов:", str(sold_total_qty), "", money(data["gross_revenue"]),
    ])
    t = Table(sales_table, colWidths=[220, 100, 100, 112])
    t.setStyle(table_style())
    elements.append(t)
    elements.append(Spacer(1, 12))

    # === 2. Возвращено билетов (Возвраты) ===
    elements.append(Paragraph("<b>2. Возвращено билетов (Возвраты)</b>", normal))
    refunds_table = [["Наименование билета / Категория", "Кол-во билетов", "Цена за билет, руб.", "Сумма возврата,руб.", "Дата возврата"]]
    for row in data["refund_rows"]:
        refunds_table.append([
            row["name"], str(row["quantity"]),
            money(row["price"]), money(row["total"]), row["date"],
        ])
    refunded_total_qty = sum(r["quantity"] for r in data["refund_rows"])
    refunds_table.append([
        "Итого возвращённых билетов:", str(refunded_total_qty), "",
        money(data["refunds_total"]), "",
    ])
    t = Table(refunds_table, colWidths=[190, 80, 100, 105, 80])
    t.setStyle(table_style())
    elements.append(t)
    elements.append(Spacer(1, 12))

    # === Финансовый итог расчёта ===
    elements.append(Paragraph("<b>Финансовый итог расчёта:</b>", normal))
    # :f — фиксированная запись без научной нотации:
    # Decimal("10").normalize() даёт "1E+1", что ломает вид строки в PDF.
    fee_percent_str = f"{Decimal(str(settings.AGENT_FEE_PERCENT)):f}"
    summary_table = [
        ["1", "Принято денежных средств от Покупателей (Валовая выручка)", money(data["gross_revenue"]) + " руб."],
        ["2", "Произведено возвратов билетов Покупателям", money(data["refunds_total"]) + " руб."],
        ["3", "Итого чистая выручка за отчетный период (стр. 1 – стр. 2)", money(data["net_revenue"]) + " руб."],
        ["4", f"Вознаграждение Агента ({fee_percent_str}% от стр. 3)", money(data["agent_fee"]) + " руб."],
        ["5", "Сумма, подлежащая перечислению Принципалу (стр. 3 – стр. 4)", money(data["payable_to_principal"]) + " руб."],
    ]
    t = Table(summary_table, colWidths=[20, 380, 132])
    t.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
        ("FONTNAME", (0, 0), (-1, -1), "DejaVuSans"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("ALIGN", (0, 0), (0, -1), "CENTER"),
        ("ALIGN", (2, 0), (2, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    elements.append(t)
    elements.append(Spacer(1, 12))

    # === Уведомление и подтверждение (54-ФЗ) ===
    elements.append(Paragraph(
        f"Настоящим Отчётом Агент уведомляет, что денежные средства в размере "
        f"{money(data['payable_to_principal'])} руб. подлежат перечислению "
        f"на банковские реквизиты Принципала.",
        normal,
    ))
    elements.append(Spacer(1, 6))
    elements.append(Paragraph(
        f"Настоящим Агент подтверждает, что при приеме денежных средств от "
        f"Покупателей за билеты кассовые чеки сформированы Агентом "
        f"({settings.AGENT_COMPANY_NAME}) в соответствии с Федеральным законом "
        f"№ 54-ФЗ с указанием признака агента и ИНН Принципала "
        f"[{principal_inn or 'ИНН Организатора'}]. Всего за отчетный период "
        f"сформировано чеков: {data['receipts_count']} шт. на общую сумму "
        f"{money(data['receipts_total'])} руб.",
        normal,
    ))

    doc.build(elements)
    buffer.seek(0)
    return buffer, data
