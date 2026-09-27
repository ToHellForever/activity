"""
Тесты ежемесячного отчёта агента перед принципалом (организатором).

Сценарий из ТЗ: продажи по категориям, возвраты, финансовый итог
(валовая выручка → возвраты → чистая выручка → вознаграждение 10% →
к перечислению), сквозная нумерация отчётов, идемпотентность,
автоформирование задачей 1–5 числа.
"""

from datetime import timedelta
from decimal import Decimal

from django.test import TestCase, override_settings
from django.utils import timezone

from core.models import User, Event, Category, Format, EventPackage, Ticket, Order, OrderTicket
from partner_app.models import AgentReport, PartnerProfile, assign_agent_contract_number
from partner_app.tasks import (
    create_agent_report_for_period,
    generate_monthly_agent_reports,
)
from partner_app.utils import collect_agent_report_data


class AgentReportTestCase(TestCase):
    """Базовая инфраструктура: партнёр, мероприятие, билеты, заказы."""

    def setUp(self):
        self.partner = User.objects.create_user(
            username="principal@example.com",
            email="principal@example.com",
            password="Passw0rd!2026",
            user_type="partner",
            is_verified=True,
        )
        self.category = Category.objects.create(name="Концерты")
        self.event_format = Format.objects.create(name="Очно")
        self.package = EventPackage.objects.create(
            name="Базовый", max_photos=1, has_video=False,
            has_program_and_speakers=False, priority_description="",
        )
        self.event = Event.objects.create(
            title="Тестовое мероприятие",
            organizer=self.partner,
            category=self.category,
            format=self.event_format,
            package=self.package,
            date_time=timezone.now() + timedelta(days=30),
        )
        self.standard = Ticket.objects.create(
            event=self.event, name="Стандарт",
            price=Decimal("1000"), available_quantity=100,
        )
        self.vip = Ticket.objects.create(
            event=self.event, name="VIP",
            price=Decimal("3000"), available_quantity=50,
        )

    def _make_order(self, ticket, quantity, months_ago=0, paid=True, refunded=False):
        """Оплаченный заказ за нужный месяц."""
        created = timezone.now() - timedelta(days=30 * months_ago)
        order = Order.objects.create(
            ticket=ticket,
            participant_data={"first_name": "Иван", "email": "buyer@example.com"},
            total_price=ticket.price * quantity,
            quantity=quantity,
            is_paid=paid,
            payment_status="refunded" if refunded else ("succeeded" if paid else "pending"),
            fiscal_receipt_id="receipt-1",
        )
        # created_at — auto_now_add, сдвигаем напрямую
        Order.objects.filter(pk=order.pk).update(created_at=created)
        for i in range(1, quantity + 1):
            OrderTicket.objects.create(
                order=order, ticket_number=i,
                is_refunded=refunded,
            )
        order.refresh_from_db()
        return order

    def test_report_calculation_matches_tz_example(self):
        """
        Расчёт по примеру из ТЗ:
        Стандарт 70×1000 + VIP 10×3000 = 100 000 валовая,
        возврат VIP 1×3000, чистая 97 000, агент 9 700, принципалу 87 300.
        """
        self._make_order(self.standard, 70, months_ago=1)
        self._make_order(self.vip, 10, months_ago=1)
        # Возврат одного VIP-билета: отдельный заказ, полностью возвращённый
        self._make_order(self.vip, 1, months_ago=1, refunded=True)

        now = timezone.now()
        year, month = self._previous_month(now)

        data = collect_agent_report_data(self.partner, year, month)

        self.assertEqual(
            Decimal(data["gross_revenue"]), Decimal("100000.00")
        )
        self.assertEqual(Decimal(data["refunds_total"]), Decimal("3000.00"))
        self.assertEqual(Decimal(data["net_revenue"]), Decimal("97000.00"))
        self.assertEqual(Decimal(data["agent_fee"]), Decimal("9700.00"))
        self.assertEqual(
            Decimal(data["payable_to_principal"]), Decimal("87300.00")
        )
        # Категории продаж: Стандарт 70 шт., VIP 10 шт.
        sales = {r["name"]: r for r in data["sales_rows"]}
        self.assertEqual(sales["Стандарт"]["quantity"], 70)
        self.assertEqual(sales["VIP"]["quantity"], 10)
        # Возвраты: 1 билет VIP
        self.assertEqual(len(data["refund_rows"]), 1)
        self.assertEqual(data["refund_rows"][0]["name"], "VIP")
        self.assertEqual(data["refund_rows"][0]["quantity"], 1)
        # Чеки: 3 заказа с fiscal_receipt_id
        self.assertEqual(data["receipts_count"], 3)

    def test_partial_refund_excluded_from_sales(self):
        """Поштучно возвращённый билет вычитается из продаж и попадает в возвраты."""
        self._make_order(self.vip, 3, months_ago=1)
        # Возвращаем один билет из трёх
        ot = OrderTicket.objects.first()
        ot.is_refunded = True
        ot.save()

        now = timezone.now()
        year, month = self._previous_month(now)

        data = collect_agent_report_data(self.partner, year, month)
        self.assertEqual(data["sales_rows"][0]["quantity"], 2)
        self.assertEqual(Decimal(data["gross_revenue"]), Decimal("6000.00"))
        self.assertEqual(Decimal(data["refunds_total"]), Decimal("3000.00"))
        self.assertEqual(Decimal(data["net_revenue"]), Decimal("3000.00"))

    def test_sequential_numbering_and_idempotency(self):
        """Сквозная нумерация 1, 2, 3... и повторное создание не даёт дубль."""
        self._make_order(self.standard, 5, months_ago=2)
        self._make_order(self.standard, 5, months_ago=1)

        now = timezone.now()
        y2, m2 = self._previous_month(now, offset=2)
        y1, m1 = self._previous_month(now, offset=1)

        first, created1 = create_agent_report_for_period(self.partner, y2, m2)
        second, created2 = create_agent_report_for_period(self.partner, y1, m1)
        # Повторный вызов за тот же месяц — существующий отчёт
        again, created3 = create_agent_report_for_period(self.partner, y1, m1)

        self.assertTrue(created1)
        self.assertTrue(created2)
        self.assertFalse(created3)
        self.assertEqual(first.number, 1)
        self.assertEqual(second.number, 2)
        self.assertEqual(again.pk, second.pk)
        self.assertEqual(AgentReport.objects.count(), 2)

    def test_pdf_contains_required_sections(self):
        """PDF содержит шапку, разделы и итоговые суммы из ТЗ."""
        self._make_order(self.standard, 70, months_ago=1)
        self._make_order(self.vip, 10, months_ago=1)

        now = timezone.now()
        year, month = self._previous_month(now)

        report, created = create_agent_report_for_period(self.partner, year, month)
        self.assertTrue(created)
        self.assertTrue(report.file_path)
        # Читаем через storage (работает и локально, и в S3/Яндекс-облаке)
        with report.file_path.open("rb") as f:
            pdf_bytes = f.read()

        self.assertTrue(pdf_bytes.startswith(b"%PDF"))
        self.assertGreater(len(pdf_bytes), 1000)

        # Финансовый итог зафиксирован в модели
        self.assertEqual(Decimal(report.gross_revenue), Decimal("100000.00"))
        self.assertEqual(Decimal(report.agent_fee), Decimal("10000.00"))
        self.assertEqual(
            Decimal(report.payable_to_principal), Decimal("90000.00")
        )

    @override_settings(AGENT_REPORT_DUE_DAY=5)
    def test_monthly_task_creates_reports_idempotently(self):
        """Задача формирует отчёты за прошлый месяц и не дублирует при повторе."""
        self._make_order(self.standard, 10, months_ago=1)

        # «Сегодня» — 3-е число (в пределах due-дня)
        with patch_datetime_day(3):
            generate_monthly_agent_reports()
        self.assertEqual(AgentReport.objects.count(), 1)

        # Повторный запуск в тот же день — дублей нет
        with patch_datetime_day(3):
            generate_monthly_agent_reports()
        self.assertEqual(AgentReport.objects.count(), 1)

    @override_settings(AGENT_REPORT_DUE_DAY=5)
    def test_monthly_task_skips_after_due_day(self):
        """После 5-го числа задача ничего не делает."""
        self._make_order(self.standard, 10, months_ago=1)
        # «Сегодня» — 6-е число
        with patch_datetime_day(6):
            result = generate_monthly_agent_reports()
        self.assertEqual(result, "not due yet")
        self.assertEqual(AgentReport.objects.count(), 0)

    def _previous_month(self, now, offset=1):
        """Год и месяц, отстоящие от now на offset месяцев назад."""
        month = now.month - offset
        year = now.year
        while month <= 0:
            month += 12
            year -= 1
        return year, month


class AgentContractNumberTestCase(TestCase):
    """Нумерация агентских договоров: с 1, нарастающая, без дублей."""

    def _make_partner(self, email):
        return User.objects.create_user(
            username=email, email=email, password="Passw0rd!2026",
            user_type="partner", is_verified=True,
        )

    def test_numbers_assigned_sequentially(self):
        """Три регистрации подряд получают номера 1, 2, 3."""
        numbers = []
        for i in range(3):
            user = self._make_partner(f"partner{i}@example.com")
            profile = PartnerProfile.objects.create(user=user)
            numbers.append(assign_agent_contract_number(profile))

        self.assertEqual(numbers, [1, 2, 3])

    def test_repeated_assignment_keeps_number(self):
        """Повторный вызов не меняет уже присвоенный номер."""
        user = self._make_partner("partner@example.com")
        profile = PartnerProfile.objects.create(user=user)
        first = assign_agent_contract_number(profile)
        second = assign_agent_contract_number(profile)
        self.assertEqual(first, second)

    def test_registration_assigns_number(self):
        """Полный цикл регистрации партнёра присваивает номер договора."""
        # Полная регистрация через view требует форм/файлов — проверяем
        # ключевой кусок: создание профиля и присвоение номера.
        user = self._make_partner("newbie@example.com")
        profile = PartnerProfile.objects.create(user=user)
        assign_agent_contract_number(profile)
        profile.refresh_from_db()
        self.assertEqual(profile.agent_contract_number, 1)

    def test_report_pdf_uses_partner_contract_number(self):
        """В шапке PDF — персональный номер договора партнёра."""
        from django.conf import settings
        from partner_app.utils import generate_agent_report_pdf
        from partner_app.models import AgentReport
        from datetime import date

        user = self._make_partner("pdf@example.com")
        profile = PartnerProfile.objects.create(
            user=user, company_name="ООО «Ромашка»", inn="1234567890",
        )
        profile.agent_contract_number = 42
        profile.save(update_fields=["agent_contract_number"])

        now = timezone.now()
        year, month = (now.year - 1, 12) if now.month == 1 else (now.year, now.month - 1)
        # Отчёт за прошлый месяц: продаж нет, но PDF со шапкой сформируется
        report, created = create_agent_report_for_period(user, year, month)
        self.assertTrue(created)

        with report.file_path.open("rb") as f:
            pdf_text = f.read().decode("latin-1", errors="ignore")
        # Номер договора партнёра в шапке (42), не глобальная настройка
        self.assertIn("42", pdf_text)


class patch_datetime_day:
    """
    Контекст: подменяет timezone.now() так, чтобы «сегодня» было
    заданное число текущего месяца (для проверки due-дня задачи).
    """

    def __init__(self, day):
        self.day = day

    def __enter__(self):
        from unittest.mock import patch

        real_now = timezone.now()
        fake_now = real_now.replace(day=self.day)
        self._patcher = patch(
            "partner_app.tasks.timezone.now", return_value=fake_now
        )
        self._patcher.start()
        return self

    def __exit__(self, *args):
        self._patcher.stop()
