from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from core.models import Order, Ticket
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth import update_session_auth_hash


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
def change_password(request):
    """Отдельная страница для смены пароля в личном кабинете посетителя."""
    if request.method == "POST":
        password_form = PasswordChangeForm(user=request.user, data=request.POST)
        if password_form.is_valid():
            password_form.save()
            update_session_auth_hash(request, password_form.user)
            messages.success(request, "Пароль успешно изменён!")
            return redirect("visitor:dashboard")
    else:
        password_form = PasswordChangeForm(user=request.user)

    return render(request, "change_password.html", {"form": password_form})


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

    # Обновляем статус заказа на "возврат"
    order.payment_status = "refunded"
    order.save()

    messages.success(request, "Билет успешно возвращён. Статус заказа обновлён.")
    return redirect("visitor:dashboard")
