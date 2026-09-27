from celery import shared_task
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils import timezone
from django.core.files.base import ContentFile
from django.db import transaction
from django.conf import settings
from datetime import timedelta, date
import calendar
from .models import ReportSchedule, SalesReport, AgentReport
from .utils import generate_sales_report, generate_agent_report_pdf
from core.models import Order, CustomUser
from core.utils import get_from_email
import logging

logger = logging.getLogger(__name__)


def create_agent_report_for_period(partner, year, month):
    """
    Создаёт ежемесячный отчёт агента для принципала (идемпотентно).

    Если отчёт за период уже существует — возвращает его, ничего не делая.
    Сквозной номер назначается в транзакции: count + 1.
    Возвращает (report, created).
    """
    with transaction.atomic():
        # Сквозной номер считаем ДО создания: number — NOT NULL
        number = AgentReport.objects.filter(partner=partner).count() + 1
        report, created = AgentReport.objects.get_or_create(
            partner=partner,
            period_year=year,
            period_month=month,
            defaults={"number": number},
        )
        if not created:
            return report, False

        pdf_buffer, data = generate_agent_report_pdf(
            partner, year, month, report.number, timezone.now().date()
        )

        # Фиксируем финансовый итог на момент формирования
        for field in (
            "gross_revenue", "refunds_total", "net_revenue",
            "agent_fee", "payable_to_principal",
            "receipts_count", "receipts_total",
        ):
            setattr(report, field, data[field])

        file_name = f"agent_report_{partner.id}_{year}-{month:02d}.pdf"
        report.file_path.save(file_name, ContentFile(pdf_buffer.getvalue()))
        report.save()
        return report, True


@shared_task
def generate_monthly_agent_reports():
    """
    Ежемесячный отчёт агента перед принципалами.

    Запускается ежедневно; с 1-го по 5-е число формирует отчёты за прошлый
    месяц для всех организаторов, у которых были продажи в этом месяце.
    Идемпотентно: повторные запуски не создают дубликаты
    (unique partner + период).
    """
    today = timezone.now().date()
    if today.day > settings.AGENT_REPORT_DUE_DAY:
        return "not due yet"

    # Прошлый месяц
    if today.month == 1:
        year, month = today.year - 1, 12
    else:
        year, month = today.year, today.month - 1

    period_start = date(year, month, 1)
    period_end = date(year, month, calendar.monthrange(year, month)[1])

    # Организаторы с оплаченными заказами за отчётный месяц
    organizer_ids = (
        Order.objects.filter(
            ticket__event__organizer__user_type="partner",
            ticket__event__organizer__is_active=True,
            is_paid=True,
            created_at__date__range=[period_start, period_end],
        )
        .values_list("ticket__event__organizer_id", flat=True)
        .distinct()
    )
    partners = CustomUser.objects.filter(id__in=organizer_ids)

    created_count = 0
    for partner in partners:
        try:
            _, created = create_agent_report_for_period(partner, year, month)
            if created:
                created_count += 1
        except Exception:
            logger.exception(
                "Ошибка формирования отчёта агента для %s (%04d-%02d)",
                partner.email, year, month,
            )
    return f"created {created_count} agent reports for {year}-{month:02d}"

@shared_task
def send_scheduled_reports():
    """
    Задача Celery для отправки отчётов по расписанию.
    """
    now = timezone.now()
    today = now.date()

    # Получаем активные расписания
    schedules = ReportSchedule.objects.filter(is_active=True)

    for schedule in schedules:
        # Проверяем, нужно ли отправлять отчёт сегодня
        if not should_send_today(schedule, today):
            continue

        # Определяем период для отчёта
        period_start, period_end = get_report_period(schedule)

        try:
            # Генерируем отчёт
            report_file = generate_sales_report(
                schedule.partner, period_start, period_end, schedule.report_format
            )

            # Сохраняем отчёт в модели
            report = SalesReport.objects.create(
                partner=schedule.partner,
                period_start=period_start,
                period_end=period_end,
                report_type=schedule.report_format,
                status="completed",
            )

            # Сохраняем файл
            file_extension = "xlsx" if schedule.report_format == "excel" else schedule.report_format
            file_name = f"report_{period_start}_{period_end}.{file_extension}"
            report.file_path.save(
                file_name,
                ContentFile(report_file.getvalue()),
            )

            # Получаем статистику для письма
            orders = Order.objects.filter(
                ticket__event__organizer=schedule.partner,
                created_at__date__range=[period_start, period_end],
            )
            refunded_orders = orders.filter(payment_status__in=["canceled", "refunded"])
            non_refunded_orders = orders.exclude(payment_status__in=["canceled", "refunded"])
            
            total_sales = sum(o.total_price for o in non_refunded_orders)
            total_tickets = sum(o.quantity for o in non_refunded_orders)
            total_refunds = sum(o.total_price for o in refunded_orders)
            total_refunded_tickets = sum(o.quantity for o in refunded_orders)

            # Рендерим HTML-шаблон
            html_context = {
                "period_start": period_start.strftime("%d.%m.%Y"),
                "period_end": period_end.strftime("%d.%m.%Y"),
                "report_format": schedule.report_format,
                "attachment_name": file_name,
                "total_sales": f"{total_sales:,.0f}".replace(",", " "),
                "total_tickets": total_tickets,
                "total_refunds": f"{total_refunds:,.0f}".replace(",", " "),
                "total_refunded_tickets": total_refunded_tickets,
                "dashboard_url": f"{settings.SITE_URL}/partner/reports/",
            }
            html_message = render_to_string(
                "emails/sales_report.html",
                html_context
            )
            plain_message = f"Добрый день!\n\nПрикрепляем отчёт о продажах за период с {period_start} по {period_end}.\n\nС уважением, ваша платформа мероприятий."

            # Отправляем email с HTML-телом
            email = EmailMultiAlternatives(
                subject=f"Отчёт о продажах с {period_start} по {period_end}",
                body=plain_message,
                from_email=get_from_email(),
                to=[schedule.email],
            )
            email.attach_alternative(html_message, "text/html")
            email.attach(
                file_name,
                report_file.getvalue(),
                f"application/{schedule.report_format}",
            )
            email.send()

            # Обновляем дату последней отправки
            schedule.last_sent = now
            schedule.save()

        except Exception as e:
            logger.error(
                "Ошибка при отправке отчёта для %s: %s",
                schedule.partner.email, str(e), exc_info=True
            )


def should_send_today(schedule, today):
    """
    Проверяет, нужно ли отправлять отчёт сегодня согласно расписанию.
    """
    if schedule.last_sent and schedule.last_sent.date() == today:
        return False

    if schedule.frequency == 'daily':
        return True

    elif schedule.frequency == 'weekly':
        if schedule.day_of_week is not None and today.weekday() == schedule.day_of_week:
            return True

    elif schedule.frequency == 'monthly':
        if schedule.day_of_month is not None and today.day == schedule.day_of_month:
            return True

    return False


def get_report_period(schedule):
    """
    Определяет период для отчёта согласно настройкам.
    """
    today = timezone.now().date()

    if schedule.period_type == 'day':
        return today, today

    elif schedule.period_type == 'week':
        # Начало недели (понедельник)
        start_of_week = today - timedelta(days=today.weekday())
        # Конец недели (воскресенье)
        end_of_week = start_of_week + timedelta(days=6)
        return start_of_week, end_of_week

    elif schedule.period_type == 'month':
        # Начало месяца
        start_of_month = today.replace(day=1)
        # Конец месяца
        if today.month == 12:
            end_of_month = today.replace(year=today.year + 1, month=1, day=1) - timedelta(days=1)
        else:
            end_of_month = today.replace(month=today.month + 1, day=1) - timedelta(days=1)
        return start_of_month, end_of_month

    elif schedule.period_type == 'custom' and schedule.custom_period_days:
        end_date = today
        start_date = end_date - timedelta(days=schedule.custom_period_days - 1)
        return start_date, end_date

    # По умолчанию - неделя
    start_of_week = today - timedelta(days=today.weekday())
    end_of_week = start_of_week + timedelta(days=6)
    return start_of_week, end_of_week