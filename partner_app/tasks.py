from celery import shared_task
from django.core.mail import EmailMessage
from django.utils import timezone
from datetime import datetime, timedelta
from .models import ReportSchedule, SalesReport
from .utils import generate_sales_report
from core.models import Order

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
            file_name = f"report_{period_start}_{period_end}.{schedule.report_format}"
            report.file_path.save(
                file_name,
                ContentFile(report_file.getvalue()),
            )

            # Отправляем email
            email = EmailMessage(
                subject=f"Отчёт о продажах с {period_start} по {period_end}",
                body=f"Добрый день!\n\nПрикрепляем отчёт о продажах за период с {period_start} по {period_end}.\n\nС уважением, ваша платформа мероприятий.",
                from_email=None,
                to=[schedule.email],
            )
            email.attach(
                file_name,
                report_file.getvalue(),
                f"application/{schedule.report_format}"
            )
            email.send()

            # Обновляем дату последней отправки
            schedule.last_sent = now
            schedule.save()

        except Exception as e:
            # Логируем ошибку и продолжаем со следующим расписанием
            print(f"Ошибка при отправке отчёта для {schedule.partner.email}: {str(e)}")


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