"""
Генерирует по одному документу каждого формата, который есть в проекте,
и отправляет их на email (по одному вложению в письме) либо сохраняет в папку.

Формируемые документы:
    1.  sales_report.csv      - отчёт о продажах (partner_app/utils.generate_csv_report)
    2.  sales_report.xlsx     - отчёт о продажах (partner_app/utils.generate_excel_report)
    3.  sales_report.pdf      - отчёт о продажах (partner_app/utils.generate_pdf_report)
    4.  participants.xlsx     - список участников (partner_app/views/reports.export_participant_list)
    5.  participants.pdf      - список участников (там же, ветка pdf)
    6.  ticket_qr.png         - QR-код заказа (partner_app/utils.generate_qr_code)
    7.  ticket.html           - билет (templates/visitor/ticket_display.html)
    8.  *_preview.pdf/.txt/.csv - результаты обработчика загрузок
                                 (core/document_storage.py, только с --with-processed)

Запуск (из корня проекта):
    python send_all_documents.py                          # на e-mail организатора
    python send_all_documents.py --to me@example.com      # на другой адрес
    python send_all_documents.py --order 804              # конкретный заказ
    python send_all_documents.py --start 2026-01-01 --end 2026-12-31
    python send_all_documents.py --dir out                # только сохранить в папку
    python send_all_documents.py --bundle                 # все документы одним письмом
    python send_all_documents.py --with-processed         # + preview.pdf / txt / csv
"""

import argparse
import base64
import io
import json
import os
import shutil
import smtplib
import sys
import tempfile
from datetime import date, datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)
# reportlab ищет DejaVuSans.ttf относительно текущей директории
os.chdir(BASE_DIR)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "activity.settings")

import django

django.setup()

import qrcode
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.mail import EmailMultiAlternatives
from django.core.validators import validate_email
from django.template.loader import render_to_string
from django.urls import reverse

from core.models import Order
from partner_app.utils import generate_qr_code, generate_sales_report
from partner_app.views.reports import export_participant_list


class Doc:
    """Готовый документ: как называется, какой MIME и сами байты."""

    def __init__(self, key, filename, content_type, data, title):
        self.key = key
        self.filename = filename
        self.content_type = content_type
        self.data = data
        self.title = title

    def __str__(self):
        return f"{self.filename} ({self.content_type}, {len(self.data)} байт)"


# --------------------------------------------------------------------------- #
#  Выбор данных                                                                #
# --------------------------------------------------------------------------- #

def pick_order(order_id=None):
    """Берёт заказ: указанный или первый оплаченный."""
    qs = Order.objects.select_related("ticket__event__organizer").order_by("-created_at")
    if order_id:
        order = qs.filter(id=order_id).first()
        if order is None:
            raise SystemExit(f"Заказ #{order_id} не найден")
        return order

    order = qs.filter(is_paid=True).first() or qs.first()
    if order is None:
        raise SystemExit("В базе нет ни одного заказа — создайте тестовые данные")
    return order


def participant_orders(event):
    """Заказы мероприятия для выгрузки списка участников (без возвратов)."""
    return (
        Order.objects.filter(ticket__event=event)
        .exclude(payment_status__in=["canceled", "refunded"])
        .select_related("ticket")
        .prefetch_related("tickets")
    )


# --------------------------------------------------------------------------- #
#  Генерация документов                                                        #
# --------------------------------------------------------------------------- #

def build_ticket_html(order):
    """Собирает контекст и рендерит HTML-билет (как visitor display_ticket)."""
    event = order.ticket.event
    participant = order.participant_data or {}
    place = (event.place_data or {}).get("address", "Место уточняется")
    organizer = event.organizer.get_full_name() or event.organizer.username
    base_url = getattr(settings, "SITE_URL", "https://bizafisha.ru").rstrip("/")
    check_link = f"{base_url}{reverse('check_ticket', args=[order.id])}"

    ticket_number_start = getattr(order, "ticket_number_start", None)
    qr_codes = []
    for i in range(order.quantity):
        current = ticket_number_start + i if ticket_number_start is not None else f"{order.id}-{i + 1}"
        payload = {
            "order_id": order.id,
            "ticket_id": str(current),
            "event_id": event.id,
            "email": participant.get("email") or "",
        }
        buffer = io.BytesIO()
        qrcode.make(json.dumps(payload, ensure_ascii=False)).save(buffer, format="PNG")
        qr_codes.append(
            {
                "qr_base64": base64.b64encode(buffer.getvalue()).decode("utf-8"),
                "qr_text": check_link,
                "ticket_number": current,
            }
        )

    return render_to_string(
        "visitor/ticket_display.html",
        {
            "order": order,
            "event": event,
            "ticket": order.ticket,
            "participant_name": participant.get("name") or "Участник",
            "email": participant.get("email") or "",
            "price": order.ticket.price,
            "place": place,
            "organizer": organizer,
            "qr_codes": qr_codes,
            "check_link": check_link,
        },
    )


def build_documents(partner, order, period_start, period_end, with_processed=False):
    """Формирует по одному документу каждого формата."""
    event = order.ticket.event
    docs = []

    # 1-3. Отчёт о продажах в трёх форматах
    for fmt, ext, mime in (
        ("csv", "csv", "text/csv"),
        ("excel", "xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
        ("pdf", "pdf", "application/pdf"),
    ):
        buffer = generate_sales_report(partner, period_start, period_end, fmt)
        data = buffer.read() if fmt == "csv" else buffer.getvalue()
        docs.append(
            Doc(
                f"sales.{ext}",
                f"sales_report_{period_start}_{period_end}.{ext}",
                mime,
                data,
                f"Отчёт о продажах за период {period_start:%d.%m.%Y} — {period_end:%d.%m.%Y}",
            )
        )

    # 4-5. Список участников
    orders = participant_orders(event)
    xlsx_response = export_participant_list(orders, event, "excel")
    docs.append(
        Doc(
            "participants.xlsx",
            f"participants_{event.id}.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            xlsx_response.content,
            f"Список участников: {event.title}",
        )
    )
    pdf_response = export_participant_list(orders, event, "pdf")
    docs.append(
        Doc(
            "participants.pdf",
            f"participants_{event.id}.pdf",
            "application/pdf",
            pdf_response.content,
            f"Список участников: {event.title}",
        )
    )

    # 6. QR-код заказа
    docs.append(
        Doc(
            "qr.png",
            f"ticket_qr_{order.id}.png",
            "image/png",
            generate_qr_code(order.id).getvalue(),
            f"QR-код заказа #{order.id}",
        )
    )

    # 7. Билет
    docs.append(
        Doc(
            "ticket.html",
            f"ticket_{order.id}.html",
            "text/html",
            build_ticket_html(order).encode("utf-8"),
            f"Билет по заказу #{order.id}",
        )
    )

    # 8. Результаты обработчика загрузок (core/document_storage.py)
    if with_processed:
        sales_xlsx = next(d for d in docs if d.key == "sales.xlsx")
        sales_pdf = next(d for d in docs if d.key == "sales.pdf")
        docs.extend(build_processed_documents(sales_pdf, sales_xlsx))

    return docs


def build_processed_documents(sales_pdf_doc, sales_xlsx_doc):
    """
    Прогоняет сгенерированные файлы через YandexDocumentProcessingStorage:
    PDF -> превью 3 страниц, XLSX -> CSV, DOCX -> TXT.
    Методы-обработчики не используют self, поэтому вызываются без экземпляра
    (экземпляр требовал бы доступов к S3).
    """
    from core.document_storage import YandexDocumentProcessingStorage as P

    import docx as docx_lib

    docs = []
    tmp_dir = tempfile.mkdtemp(prefix="docs_")

    try:
        # PDF -> превью первых 3 страниц
        pdf_path = os.path.join(tmp_dir, "source.pdf")
        with open(pdf_path, "wb") as fh:
            fh.write(sales_pdf_doc.data)
        out_pdf = P._process_pdf(None, pdf_path, os.path.join(tmp_dir, "source"))
        with open(out_pdf, "rb") as fh:
            docs.append(
                Doc(
                    "processed.pdf",
                    "document_storage_preview.pdf",
                    "application/pdf",
                    fh.read(),
                    "PDF после обработчика: первые 3 страницы",
                )
            )

        # XLSX -> CSV первого листа
        xlsx_path = os.path.join(tmp_dir, "source.xlsx")
        with open(xlsx_path, "wb") as fh:
            fh.write(sales_xlsx_doc.data)
        out_csv = P._process_xlsx(None, xlsx_path, os.path.join(tmp_dir, "source"))
        with open(out_csv, "rb") as fh:
            docs.append(
                Doc(
                    "processed.csv",
                    "document_storage_xlsx_to_csv.csv",
                    "text/csv",
                    fh.read(),
                    "XLSX после обработчика: первый лист в CSV",
                )
            )

        # DOCX -> TXT (исходник создаём на месте, в проекте DOCX только читают)
        source_docx = docx_lib.Document()
        source_docx.add_paragraph("Документ партнёра: тест конвертации DOCX в TXT.")
        docx_path = os.path.join(tmp_dir, "source.docx")
        source_docx.save(docx_path)
        out_txt = P._process_docx(None, docx_path, os.path.join(tmp_dir, "source"))
        with open(out_txt, "rb") as fh:
            docs.append(
                Doc(
                    "processed.txt",
                    "document_storage_docx_to_txt.txt",
                    "text/plain",
                    fh.read(),
                    "DOCX после обработчика: текст в TXT",
                )
            )
    finally:
        # openpyxl в read_only режиме может держать handle, поэтому удаляем с ignore_errors
        shutil.rmtree(tmp_dir, ignore_errors=True)

    return docs


# --------------------------------------------------------------------------- #
#  Отправка / сохранение                                                       #
# --------------------------------------------------------------------------- #

def send_one(doc, recipient, label=""):
    email = EmailMultiAlternatives(
        subject=f"{label}{doc.filename}",
        body=f"{doc.title}\n\nФайл: {doc.filename}\nФормат: {doc.content_type}",
        from_email=settings.DEFAULT_FROM_EMAIL or settings.EMAIL_HOST_USER,
        to=[recipient],
    )
    email.attach(doc.filename, doc.data, doc.content_type)
    return email.send(fail_silently=False)


def send_bundle(docs, recipient):
    email = EmailMultiAlternatives(
        subject=f"Документы платформы: {len(docs)} файлов",
        body="Во вложении по одному документу каждого формата:\n\n"
        + "\n".join(f"- {d.title} ({d.filename})" for d in docs),
        from_email=settings.DEFAULT_FROM_EMAIL or settings.EMAIL_HOST_USER,
        to=[recipient],
    )
    for doc in docs:
        email.attach(doc.filename, doc.data, doc.content_type)
    return email.send(fail_silently=False)


def save_document(doc, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, doc.filename)
    with open(path, "wb") as fh:
        fh.write(doc.data)
    return path


def check_email(address, what):
    """Проверяет e-mail и выходит с понятной ошибкой, если он некорректен."""
    try:
        validate_email(address or "")
    except ValidationError:
        raise SystemExit(
            f"Некорректный {what}: {address!r}\n"
            f"Проверьте адрес — SMTP отклонит его с ошибкой 501 'Bad recipient address syntax'."
        )


def describe_smtp_error(exc):
    """Достаёт из smtplib-исключения текст ответа сервера."""
    if isinstance(exc, smtplib.SMTPRecipientsRefused):
        for address, (code, detail) in exc.recipients.items():
            hint = ""
            if code == 501 or b"address syntax" in detail:
                hint = "\nПодсказка: адрес указан неверно — нужен полный домен, например user@yandex.ru"
            return f"Сервер отклонил получателя {address}: {code} {detail.decode(errors='replace')}{hint}"
    return str(exc)


# --------------------------------------------------------------------------- #
#  Точка входа                                                                 #
# --------------------------------------------------------------------------- #

def parse_args():
    parser = argparse.ArgumentParser(description="Отправка по одному документу каждого формата")
    parser.add_argument("--to", help="Получатель (по умолчанию — e-mail организатора заказа)")
    parser.add_argument("--order", type=int, help="ID заказа (по умолчанию — последний оплаченный)")
    parser.add_argument("--partner", help="E-mail партнёра-организатора для отчёта о продажах")
    parser.add_argument("--start", help="Начало периода отчёта, YYYY-MM-DD")
    parser.add_argument("--end", help="Конец периода отчёта, YYYY-MM-DD")
    parser.add_argument("--dir", help="Сохранить файлы в папку и не отправлять")
    parser.add_argument("--bundle", action="store_true", help="Все документы одним письмом")
    parser.add_argument(
        "--test-email",
        action="store_true",
        help="Не отправлять реально: использовать locmem-бэкенд и показать результат",
    )
    parser.add_argument("--with-processed", action="store_true", help="Добавить результаты document_storage")
    return parser.parse_args()


def main():
    args = parse_args()

    order = pick_order(args.order)
    event = order.ticket.event
    partner = event.organizer

    if args.partner:
        from django.contrib.auth import get_user_model

        partner = get_user_model().objects.filter(email=args.partner).first()
        if partner is None:
            raise SystemExit(f"Пользователь с e-mail {args.partner} не найден")

    today = date.today()
    period_start = datetime.strptime(args.start, "%Y-%m-%d").date() if args.start else today.replace(day=1)
    period_end = datetime.strptime(args.end, "%Y-%m-%d").date() if args.end else today

    recipient = args.to or partner.email
    check_email(recipient, "адрес получателя (--to или e-mail организатора)")

    if args.test_email:
        settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

    print(f"Заказ:        #{order.id} — {event.title}")
    print(f"Организатор:  {partner.email}")
    print(f"Период:       {period_start} — {period_end}")
    print(f"Получатель:   {recipient}")
    if args.test_email:
        print("Режим:        ТЕСТ (locmem, письма не уходят на SMTP)")
    print("-" * 60)

    docs = build_documents(partner, order, period_start, period_end, args.with_processed)

    if args.dir:
        for doc in docs:
            print(f"[OK]   {doc.title} -> {save_document(doc, args.dir)}")
        print("-" * 60)
        print(f"Сохранено документов: {len(docs)}")
        return

    ok = 0
    if args.bundle:
        try:
            send_bundle(docs, recipient)
            ok = len(docs)
            print(f"[OK]   одно письмо с {len(docs)} вложениями отправлено")
        except Exception as exc:
            print(f"[FAIL] письмо не отправлено: {describe_smtp_error(exc)}")
    else:
        for index, doc in enumerate(docs, 1):
            try:
                send_one(doc, recipient, label=f"[{index}/{len(docs)}] ")
                ok += 1
                print(f"[OK]   {doc.title} -> {doc}")
            except smtplib.SMTPRecipientsRefused as exc:
                print(f"[FAIL] {doc.title}: {describe_smtp_error(exc)}")
                print("Получатель отклонён сервером, дальше не продолжаем.")
                break
            except Exception as exc:
                print(f"[FAIL] {doc.title}: {describe_smtp_error(exc)}")

    print("-" * 60)
    print(f"Отправлено писем: {ok} из {len(docs)}")

    if args.test_email:
        from django.core import mail

        print(f"В locmem-очереди писем: {len(mail.outbox)}")
        for message in mail.outbox:
            names = ", ".join(att[0] for att in message.attachments)
            print(f"  - {message.subject} | вложения: {names}")


if __name__ == "__main__":
    main()
