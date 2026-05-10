# -*- coding: utf-8 -*-
"""
Кастомная команда Django для мониторинга гонок в системе покупки билетов.
Запускается через: python manage.py check_race_conditions
"""

from django.core.management.base import BaseCommand
from django.db.models import Count
from core.models import Ticket, Order
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Проверяет базу данных на наличие проблем, связанных с гонками"

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("=== Starting Race Condition Check ==="))

        issues_found = False

        # 1. Проверка билетов с отрицательным количеством
        negative_tickets = Ticket.objects.annotate(
            sold=Count("orders__quantity")
        ).filter(available_quantity__lt=0)

        if negative_tickets.exists():
            self.stdout.write(
                self.style.ERROR(
                    f"❌ Found {negative_tickets.count()} tickets with negative available quantity!"
                )
            )
            for ticket in negative_tickets:
                self.stdout.write(
                    self.style.WARNING(
                        f"  - Ticket ID:{ticket.id} ({ticket.name}): {ticket.available_quantity}"
                    )
                )
            issues_found = True
        else:
            self.stdout.write(
                self.style.SUCCESS("✅ No tickets with negative quantity found")
            )

        # 2. Проверка билетов, где продано больше, чем доступно
        oversold_tickets = []
        for ticket in Ticket.objects.all():
            sold = sum(order.quantity for order in ticket.orders.all())
            if sold > ticket.available_quantity:
                oversold_tickets.append((ticket, sold))

        if oversold_tickets:
            self.stdout.write(
                self.style.ERROR(f"❌ Found {len(oversold_tickets)} oversold tickets!")
            )
            for ticket, sold in oversold_tickets:
                self.stdout.write(
                    self.style.WARNING(
                        f"  - Ticket ID:{ticket.id} ({ticket.name}): "
                        f"Sold: {sold}, Available: {ticket.available_quantity}"
                    )
                )
            issues_found = True
        else:
            self.stdout.write(self.style.SUCCESS("✅ No oversold tickets found"))

        # 3. Проверка заказов без билетов
        orders_without_tickets = Order.objects.filter(ticket__isnull=True)
        if orders_without_tickets.exists():
            self.stdout.write(
                self.style.ERROR(
                    f"❌ Found {orders_without_tickets.count()} orders without tickets!"
                )
            )
            issues_found = True
        else:
            self.stdout.write(self.style.SUCCESS("✅ No orders without tickets found"))

        # 4. Проверка согласованности количества
        inconsistent_tickets = []
        for ticket in Ticket.objects.all():
            db_sold = sum(order.quantity for order in ticket.orders.all())
            calc_available = ticket.available_quantity - db_sold

            # Проверяем через метод модели
            try:
                model_available = ticket.get_available_count()
                if calc_available != model_available:
                    inconsistent_tickets.append(
                        (ticket, db_sold, calc_available, model_available)
                    )
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f"❌ Error checking ticket {ticket.id}: {str(e)}")
                )
                issues_found = True

        if inconsistent_tickets:
            self.stdout.write(
                self.style.ERROR(
                    f"❌ Found {len(inconsistent_tickets)} tickets with calculation inconsistencies!"
                )
            )
            for (
                ticket,
                db_sold,
                calc_available,
                model_available,
            ) in inconsistent_tickets:
                self.stdout.write(
                    self.style.WARNING(
                        f"  - Ticket ID:{ticket.id}: DB Sold={db_sold}, "
                        f"Calculated={calc_available}, Model={model_available}"
                    )
                )
            issues_found = True
        else:
            self.stdout.write(
                self.style.SUCCESS("✅ No calculation inconsistencies found")
            )

        # 5. Проверка транзакционной целостности
        try:
            from django.db import transaction

            with transaction.atomic():
                # Просто проверяем, что транзакции работают
                test_ticket = Ticket.objects.first()
                if test_ticket:
                    test_ticket.get_available_count()
            self.stdout.write(
                self.style.SUCCESS("✅ Transaction system is working correctly")
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"❌ Transaction system error: {str(e)}")
            )
            issues_found = True

        # Итоговый отчет
        if issues_found:
            self.stdout.write(self.style.ERROR("\n❌ RACE CONDITION ISSUES DETECTED!"))
            self.stdout.write(self.style.WARNING("  Run fixes or investigate manually"))
        else:
            self.stdout.write(
                self.style.SUCCESS("\n✅ No race condition issues detected")
            )

        self.stdout.write(self.style.SUCCESS("=== Race Condition Check Complete ==="))
