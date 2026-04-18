from celery import shared_task
from django.core.mail import EmailMessage
from django.utils import timezone
from datetime import datetime, timedelta
from .models import SalesReport
from .utils import generate_sales_report
from core.models import CustomUser

@shared_task
def send_weekly_sales_reports():
    """
    Еженедельная задача для генерации и отправки отчётов о продажах партнёрам.
    """
    # Получаем всех партнёров
    partners = CustomUser.objects.filter(user_type="partner")

    # Определяем период (прошлая неделя)
    today = timezone.now().date()
    period_end = today - timedelta(days=1)
    period_start = period_end - timedelta(days=6)

    for partner in partners:
        try:
            # Генерируем отчёт в формате PDF
            report_file = generate_sales_report(
                partner, period_start, period_end, "pdf"
            )

            # Сохраняем отчёт в модели
            report = SalesReport.objects.create(
                partner=partner,
                period_start=period_start,
                period_end=period_end,
                report_type="pdf",
                status="completed",
            )

            # Сохраняем файл
            file_name = f"weekly_report_{period_start}_{period_end}.pdf"
            report.file_path.save(
                file_name,
                ContentFile(report_file.getvalue()),
            )

            # Отправляем письмо с отчётом
            email = EmailMessage(
                subject=f"Еженедельный отчёт о продажах с {period_start} по {period_end}",
                body=f"Здравствуйте, {partner.get_full_name()}!\n\n"
                     f"Прикрепляем еженедельный отчёт о ваших продажах.\n\n"
                     f"С уважением,\nВаша команда поддержки",
                to=[partner.email],
            )
            email.attach(
                file_name,
                report_file.getvalue(),
                "application/pdf"
            )
            email.send()

        except Exception as e:
            print(f"Ошибка при генерации отчёта для {partner.email}: {str(e)}")
            continue