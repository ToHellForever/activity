from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from django.utils import timezone
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from core.models import Order, Ticket, Event
import json
import uuid
from yookassa import Configuration, Payment

# Настройка ЮКассы
Configuration.account_id = settings.YOOKASSA_SHOP_ID
Configuration.secret_key = settings.YOOKASSA_SECRET_KEY


def send_order_confirmation_email(order):
    """
    Отправка уведомления на почту с информацией о заказе и QR-кодами.
    """
    participant_email = order.participant_data.get("email")
    if not participant_email:
        return

    # Формирование контекста для шаблона письма
    context = {
        "order": order,
        "ticket": order.ticket,
        "participant_data": order.participant_data,
        "qr_codes": order.qr_codes,
    }

    # Рендеринг HTML-шаблона письма
    email_html = render_to_string("emails/ticket_confirmation.html", context)

    # Отправка письма
    send_mail(
        subject=f"Подтверждение заказа #{order.id}",
        message=f"Ваш заказ #{order.id} успешно оплачен. QR-коды прикреплены к письму.",
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[participant_email],
        html_message=email_html,
        fail_silently=False,
    )

def send_reservation_email(order, request):
    """
    Отправка письма с кнопкой для оплаты забронированного билета.
    """
    participant_email = order.participant_data.get("email")
    if not participant_email:
        return

    # Формирование контекста для шаблона письма
    context = {
        "order": order,
        "ticket": order.ticket,
        "participant_data": order.participant_data,
        "payment_url": request.build_absolute_uri(f"/payment/pay_reserved/{order.id}/"),
    }

    # Рендеринг HTML-шаблона письма
    email_html = render_to_string("emails/order_confirmation.html", context)

    # Отправка письма
    send_mail(
        subject=f"Бронирование билета #{order.id}",
        message=f"Ваш билет #{order.id} забронирован. Для оплаты перейдите по ссылке: {request.build_absolute_uri(f'/payment/pay_reserved/{order.id}/')}",
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[participant_email],
        html_message=email_html,
        fail_silently=False,
    )


def create_payment(request, ticket_id):
    """
    Создание платежа в ЮКассе для покупки билета или бронирование без оплаты.
    """
    import traceback
    if request.method != "POST":
        return JsonResponse({"error": "Метод не поддерживается"}, status=405)

    try:
        print("POST data:", request.POST)
        print("Ticket ID:", ticket_id)
        ticket = get_object_or_404(Ticket, id=ticket_id)
        quantity = int(request.POST.get("quantity", 1))

        if not ticket.is_available() or ticket.get_available_count() < quantity:
            return JsonResponse({"error": f"Запрошенное количество билетов {ticket.name} недоступно"}, status=400)

        # Данные участника из формы
        participant_data = {
            "name": request.POST.get("name"),
            "email": request.POST.get("email"),
            "phone": request.POST.get("phone"),
        }

        total_price = ticket.price * quantity

        # Проверка, выбран ли чекбокс "Забронировать без оплаты"
        reserve_without_payment = request.POST.get("reserve_without_payment") == "on"

        # Создание заказа
        order = Order.objects.create(
            ticket=ticket,
            participant_data=participant_data,
            total_price=total_price,
            quantity=quantity,
            payment_status="reserved" if reserve_without_payment else "pending",
        )

        if reserve_without_payment:
            # Отправка письма с кнопкой для оплаты
            send_reservation_email(order, request)
            return JsonResponse({
                "success": True,
                "redirect_url": f"/payment/success/{order.id}/"
            })
        else:
            # Создание платежа в ЮКассе
            payment = Payment.create(
                {
                    "amount": {"value": str(total_price), "currency": "RUB"},
                    "confirmation": {
                        "type": "redirect",
                        "return_url": request.build_absolute_uri(
                            f"/payment/success/{order.id}/"
                        ),
                    },
                    "capture": True,
                    "description": f"Оплата заказа #{order.id} для мероприятия {ticket.event.title}",
                    "metadata": {"order_id": order.id},
                },
                uuid.uuid4(),
            )

            # Сохранение идентификатора платежа в ЮКассе для заказа
            order.yookassa_payment_id = payment.id
            order.save()

            return JsonResponse(
                {"payment_url": payment.confirmation.confirmation_url, "order_id": order.id}
            )

    except Exception as e:
        traceback.print_exc()
        return JsonResponse({"error": str(e)}, status=500)


@csrf_exempt
def yookassa_webhook(request):
    """
    Обработка уведомлений от ЮКассы (вебхуки).
    """
    try:
        # Получение и проверка данных из вебхука
        event_json = json.loads(request.body)
        if event_json["event"] == "payment.succeeded":
            payment = event_json["object"]
            order = Order.objects.get(yookassa_payment_id=payment["id"])
            order.payment_status = "succeeded"
            order.is_paid = True
            order.yookassa_payment_data = payment
            order.save()

            # Отправка уведомления на почту
            send_order_confirmation_email(order)

        elif event_json["event"] == "payment.canceled":
            payment = event_json["object"]
            order = Order.objects.get(yookassa_payment_id=payment["id"])
            order.payment_status = "canceled"
            order.save()

        elif event_json["event"] == "refund.succeeded":
            payment = event_json["object"]
            order = Order.objects.get(yookassa_payment_id=payment["payment_id"])
            order.payment_status = "refunded"
            order.save()

        return HttpResponse(status=200)

    except Exception as e:
        print(f"Error in yookassa_webhook: {e}")
        return HttpResponse(status=400)


def refund_ticket(request, order_id):
    """
    Возврат билета через ЮКассу.
    """
    import traceback
    try:
        print("Starting refund process for order_id:", order_id)
        order = get_object_or_404(Order, id=order_id)
        print("Order found:", order.id, "Status:", order.payment_status, "YooKassa Payment ID:", order.yookassa_payment_id)

        if order.payment_status != "succeeded":
            return render(request, "refund_error.html", {"error": "Заказ не оплачен"})

        # Проверка срока возврата
        if order.ticket.event.get_refund_deadline() < timezone.now():
            return render(request, "refund_error.html", {"error": "Срок возврата истек"})

        print("Attempting to refund payment with ID:", order.yookassa_payment_id)
        from yookassa import Refund
        # Создание возврата в ЮКассе
        refund = Refund.create(
            {"payment_id": order.yookassa_payment_id, "amount": {"value": str(order.total_price), "currency": "RUB"}},
            uuid.uuid4()
        )
        print("Refund created successfully:", refund.id)

        # Обновление статуса заказа
        order.payment_status = "refunded"
        order.save()
        print("Order status updated to 'refunded'")

        return render(request, "refund_success.html")

    except Exception as e:
        traceback.print_exc()
        return render(request, "refund_error.html", {"error": str(e)})


def payment_success(request, order_id):
    """
    Страница успешной оплаты.
    """
    order = get_object_or_404(Order, id=order_id)
    return render(request, "payment_success.html", {"order": order})

def pay_reserved_order(request, order_id):
    """
    Оплата забронированного билета.
    """
    import traceback
    try:
        order = get_object_or_404(Order, id=order_id)

        if order.payment_status != "reserved":
            return render(request, "refund_error.html", {"error": "Этот заказ не может быть оплачен"})

        # Создание платежа в ЮКассе
        payment = Payment.create(
            {
                "amount": {"value": str(order.total_price), "currency": "RUB"},
                "confirmation": {
                    "type": "redirect",
                    "return_url": request.build_absolute_uri(
                        f"/payment/success/{order.id}/"
                    ),
                },
                "capture": True,
                "description": f"Оплата заказа #{order.id} для мероприятия {order.ticket.event.title}",
                "metadata": {"order_id": order.id},
            },
            uuid.uuid4(),
        )

        # Сохранение идентификатора платежа в ЮКассе для заказа
        order.yookassa_payment_id = payment.id
        order.payment_status = "pending"
        order.save()

        return redirect(payment.confirmation.confirmation_url)

    except Exception as e:
        traceback.print_exc()
        return render(request, "refund_error.html", {"error": str(e)})
