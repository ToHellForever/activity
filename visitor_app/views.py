from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from core.models import Order, Ticket


@login_required
def visitor_dashboard(request):
    # Проверяем тип пользователя
    if request.user.user_type != "visitor":
        # Если зашел партнер, перенаправляем его на его кабинет
        return redirect("partner:dashboard")

    # Получаем заказы текущего пользователя по email
    user_orders = (
        Order.objects.filter(participant_data__email=request.user.email)
        .select_related("ticket__event")
        .order_by("-created_at")
    )

    # Логика для посетителя
    context = {"user": request.user, "user_orders": user_orders, "now": timezone.now()}
    return render(request, "visitor/dashboard.html", context)


@login_required
def refund_ticket(request, order_id):
    """
    Обработка возврата билета.
    """
    order = get_object_or_404(
        Order, id=order_id, participant_data__email=request.user.email
    )

    # Проверяем, можно ли вернуть билет
    refund_deadline = order.ticket.event.get_refund_deadline()
    if refund_deadline <= timezone.now():
        messages.error(request, "Срок возврата билета истёк.")
        return redirect("visitor:dashboard")

    # Удаляем заказ (это автоматически обновит количество проданных билетов через метод get_sold_count)
    order.delete()

    messages.success(request, "Билет успешно возвращён.")
    return redirect("visitor:dashboard")
