import os
import sys
from datetime import datetime, timedelta
from django.conf import settings

# Настраиваем Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "activity.settings")
import django
django.setup()

from django.contrib.auth import get_user_model
from partner_app.utils import generate_sales_report

def generate_all_reports_for_partner(partner_id, period_start, period_end):
    """
    Генерирует отчёты во всех форматах для указанного партнёра и периода.
    """
    User = get_user_model()
    partner = User.objects.get(id=partner_id)

    # Форматы отчётов
    report_formats = ["pdf", "csv", "excel"]

    # Директория для сохранения отчётов
    reports_dir = os.path.join(settings.BASE_DIR, "media", "reports")
    os.makedirs(reports_dir, exist_ok=True)

    for report_format in report_formats:
        try:
            # Генерируем отчёт
            report_file = generate_sales_report(
                partner, period_start, period_end, report_format
            )

            # Формируем имя файла
            file_name = f"report_{period_start}_{period_end}.{report_format}"
            file_path = os.path.join(reports_dir, file_name)

            # Сохраняем файл
            with open(file_path, "wb") as f:
                f.write(report_file.getvalue())

            print(f"Отчёт успешно сгенерирован и сохранён: {file_path}")

        except Exception as e:
            print(f"Ошибка при генерации отчёта в формате {report_format}: {e}")

if __name__ == "__main__":
    # Пример: генерация отчётов для партнёра с ID=12 за последние 30 дней
    partner_id = 12  # ID партнёра
    period_end = datetime.now().date()
    period_start = period_end - timedelta(days=30)

    generate_all_reports_for_partner(partner_id, period_start, period_end)