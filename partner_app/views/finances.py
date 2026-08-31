"""Финансы партнёра: выручка, комиссия, выплаты, реквизиты."""
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Sum, F, ExpressionWrapper, DecimalField

from core.models import Order, PayoutRequest, PayoutDetails
from ..forms import PayoutDetailsForm
from .decorators import check_partner_status, get_rejection_messages


def get_partner_revenue_and_commission(user):
    """
    Единая точка расчёта выручки и комиссии платформы партнёра.
    Учитываются только оплаченные заказы, исключая возвраты.
    Возвращает кортеж (total_revenue, commission_sum).
    """
    orders = Order.objects.filter(ticket__event__organizer=user)
    paid_orders = orders.filter(is_paid=True).exclude(payment_status="refunded")

    total_revenue = paid_orders.aggregate(total=Sum("total_price"))["total"] or 0

    commission_sum = (
        paid_orders.annotate(
            event_commission=ExpressionWrapper(
                F("total_price") * (F("ticket__event__commission_rate") / 100),
                output_field=DecimalField(),
            )
        )
        .aggregate(total_commission=Sum("event_commission"))["total_commission"]
        or 0
    )

    return total_revenue, commission_sum


@login_required
def finances(request):
    total_revenue, commission_sum = get_partner_revenue_and_commission(request.user)

    # Сумма к выплате: выручка минус комиссия минус заявки в обработке (pending/processing)
    pending_amount = (
        PayoutRequest.objects.filter(
            organizer=request.user,
            status__in=["pending", "processing"]
        ).aggregate(total=Sum("amount"))["total"]
        or 0
    )
    # Также вычитаем уже выплаченные суммы (paid) — они уже ушли партнёру
    paid_amount = (
        PayoutRequest.objects.filter(
            organizer=request.user,
            status="paid"
        ).aggregate(total=Sum("amount"))["total"]
        or 0
    )
    payout_amount = total_revenue - commission_sum - pending_amount - paid_amount

    payout_history = PayoutRequest.objects.filter(organizer=request.user).order_by(
        "-created_at"
    )

    # Получаем реквизиты партнёра
    partner_payout_details = PayoutDetails.objects.filter(partner=request.user)

    context = {
        "total_revenue": total_revenue,
        "commission_amount": commission_sum,
        "payout_amount": float(payout_amount),
        "payout_history": payout_history,
        "partner_payout_details": partner_payout_details,
    }
    context["rejection_messages"] = get_rejection_messages(request)
    return render(request, "partner/finances.html", context)


@require_POST
@csrf_exempt
@check_partner_status('can_request_payments')
def request_payout(request):
    """
    Обработка AJAX-запроса на создание запроса выплаты.
    """
    try:
        data = request.POST
        amount_str = data.get("amount", "0").replace(",", ".")
        amount = float(amount_str)
        payout_details_id = data.get("payout_details")
        comment = data.get("comment", "")

        if not payout_details_id:
            return JsonResponse(
                {
                    "status": "error",
                    "message": "Пожалуйста, выберите реквизиты для выплаты",
                },
                status=400,
            )

        try:
            payout_details = PayoutDetails.objects.get(
                id=payout_details_id, partner=request.user
            )
        except ObjectDoesNotExist:
            return JsonResponse(
                {"status": "error", "message": "Выбранные реквизиты не найдены"},
                status=404,
            )

        # Получаем доступную для выплаты сумму
        total_revenue, commission_sum = get_partner_revenue_and_commission(request.user)
        payout_amount = total_revenue - commission_sum

        # Серверная валидация суммы выплаты
        if amount > payout_amount:
            return JsonResponse(
                {
                    "status": "error",
                    "message": f"Сумма выплаты не может превышать доступную сумму: {payout_amount:.2f} ₽",
                },
                status=400,
            )

        # Сохраняем баланс партнёра на момент запроса
        balance_at_request = payout_amount

        # Создаём запрос на выплату со статусом "processing"
        PayoutRequest.objects.create(
            organizer=request.user,
            amount=amount,
            payment_details=payout_details,
            comment=comment,
            status="processing",
            balance_at_request=balance_at_request,
        )

        return JsonResponse(
            {"status": "success", "message": "Запрос на выплату успешно создан!"}
        )

    except Exception as e:
        return JsonResponse(
            {"status": "error", "message": f"Произошла ошибка: {str(e)}"}, status=500
        )


@login_required
@check_partner_status('can_request_payments')
def payout_details(request):
    """
    Страница для добавления, просмотра, редактирования и удаления
    реквизитов для выплат.
    """
    details = PayoutDetails.objects.filter(partner=request.user)

    if request.method == "POST":
        action = request.POST.get("action")

        # === УДАЛЕНИЕ ===
        if action == "delete":
            detail_id = request.POST.get("detail_id")
            try:
                detail = PayoutDetails.objects.get(
                    id=detail_id, partner=request.user
                )
                detail.delete()
                messages.success(request, "Реквизиты успешно удалены!")
            except PayoutDetails.DoesNotExist:
                messages.error(request, "Реквизит не найден.")
            return redirect("partner:payout_details")

        # === РЕДАКТИРОВАНИЕ (AJAX) ===
        if action == "edit":
            detail_id = request.POST.get("detail_id")
            try:
                detail = PayoutDetails.objects.get(
                    id=detail_id, partner=request.user
                )
                detail.bank_name = request.POST.get("bank_name", detail.bank_name)
                detail.account_number = request.POST.get("account_number", detail.account_number)
                detail.account_holder = request.POST.get("account_holder", detail.account_holder)
                detail.bik = request.POST.get("bik", detail.bik) or None
                detail.save()
                return JsonResponse(
                    {"status": "success", "message": "Реквизиты обновлены"}
                )
            except PayoutDetails.DoesNotExist:
                return JsonResponse(
                    {"status": "error", "message": "Реквизит не найден."},
                    status=404,
                )

        # === СОЗДАНИЕ ===
        form = PayoutDetailsForm(request.POST)
        if form.is_valid():
            payout_detail = form.save(commit=False)
            payout_detail.partner = request.user
            payout_detail.save()
            messages.success(request, "Реквизиты успешно сохранены!")
            return redirect("partner:payout_details")
    else:
        form = PayoutDetailsForm()

    partner_profile = getattr(request.user, "partner_profile", None)
    context = {
        "form": form,
        "details": details,
        "rejection_messages": get_rejection_messages(request),
        "partner_profile": partner_profile,
    }
    return render(request, "partner/payout_details.html", context)


@login_required
@require_POST
def set_default_payout_detail(request):
    """Установить реквизиты как основные."""
    detail_id = request.POST.get("detail_id")
    try:
        detail = PayoutDetails.objects.get(id=detail_id, partner=request.user)
        # Сбросим все is_default
        PayoutDetails.objects.filter(partner=request.user).update(is_default=False)
        detail.is_default = True
        detail.save()
        return JsonResponse({"status": "success"})
    except PayoutDetails.DoesNotExist:
        return JsonResponse(
            {"status": "error", "message": "Реквизит не найден."}, status=404
        )
