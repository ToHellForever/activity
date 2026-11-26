from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib import messages
from django.http import JsonResponse, HttpResponse, Http404, HttpResponseForbidden
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from django.utils import timezone
from django.core.mail import send_mail, EmailMultiAlternatives
import logging
from django.template.loader import render_to_string
from core.models import (
    Order,
    Ticket,
    Event,
    EventPackage,
    UserPackageSubscription,
    OrderTicket,
    RobokassaPayment,
    RobokassaRefund,
)
from core.services import (
    reserve_tickets,
    bulk_reserve_tickets,
    cancel_unpaid_order,
    TicketReservationError,
)
from core.utils import get_from_email
from django.db import transaction, models
from django.db.models import Sum
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
import json
from .robokassa import (
    RefundRejectedError,
    build_payment_url,
    build_receipt,
    create_refund,
    get_operation_details,
    verify_result_signature,
)
from datetime import timedelta
from decimal import Decimal, InvalidOperation

logger = logging.getLogger(__name__)


def _create_robokassa_payment(orders, amount, description, email):
    amount = Decimal(str(amount)).quantize(Decimal("0.01"))
    receipt, order_items = build_receipt(orders)
    with transaction.atomic():
        payment = RobokassaPayment.objects.create(
            amount=amount,
            receipt_data={"receipt": receipt, "order_items": order_items},
        )
        payment.orders.add(*orders)
        for order in orders:
            order.payment_id = str(payment.pk)
            order.save(update_fields=["payment_id"])

        payment_url = build_payment_url(
            payment.pk,
            amount,
            description,
            email=email,
            receipt=receipt,
            expiration_date=payment.created_at + timedelta(minutes=15),
        )
    return payment, payment_url


def _send_orders_confirmation_email(orders, request=None):
    """
    Общий хелпер: отправка ОДНОГО письма подтверждения для списка заказов.
    Если заказов несколько (покупка нескольких типов билетов) — в письме
    будет блок «Информация о заказе» и QR-коды по каждому заказу.
    """
    if not orders:
        return
    first = orders[0]
    participant_email = first.participant_data.get("email")
    if not participant_email:
        logger.warning('[email] Email участника пуст для заказа %s', first.id)
        return

    # Генерируем QR-коды "на лету" для каждого заказа
    base_url = getattr(settings, 'SITE_URL', request.build_absolute_uri('/')[:-1] if request else 'https://bizafisha.ru')
    order_blocks = []
    for order in orders:
        order_blocks.append({
            "order": order,
            "ticket": order.ticket,
            "qr_codes": order.generate_qr_data(base_url=base_url),
        })
    logger.info('[email] QR-коды сгенерированы для %d заказов', len(order_blocks))

    # Тема: №818 или №818, №819, №820
    ids = ", ".join(f"№{o.id}" for o in orders)
    total_price = sum(o.total_price for o in orders)

    context = {
        "orders": orders,
        "order_blocks": order_blocks,
        "order": first,
        "ticket": first.ticket,
        "participant_data": first.participant_data,
        "order_ids": ids,
        "total_price": total_price,
        "request": request,
        "site_name": "Платформа мероприятий",
        "now": timezone.now(),
    }

    email_html = render_to_string("emails/order_confirmation.html", context)

    email_message = EmailMultiAlternatives(
        subject=f"Подтверждение заказа {ids}",
        body=f"Ваш заказ {ids} успешно оплачен.",
        from_email=get_from_email("tickets"),
        to=[participant_email],
    )
    email_message.attach_alternative(email_html, "text/html")

    if email_message.send(fail_silently=False) != 1:
        raise RuntimeError("Письмо с подтверждением заказа не было отправлено.")
    logger.info('[email] Письмо отправлено для заказов %s на %s', ids, participant_email)


def send_order_confirmation_email(order, request=None):
    """
    Отправка уведомления на почту с информацией о заказе.
    QR-коды генерируются на лету и вставляются как base64 в письмо.
    """
    _send_orders_confirmation_email([order], request)


def send_reservation_email(order, request):
    """
    Отправка письма с кнопкой для оплаты забронированного билета.
    """
    participant_email = order.participant_data.get("email")
    if not participant_email:
        raise ValueError(f"У заказа #{order.pk} не указан email для бронирования.")

    # Формирование контекста для шаблона письма
    context = {
        "order": order,
        "ticket": order.ticket,
        "participant_data": order.participant_data,
        "payment_url": request.build_absolute_uri(f"/payment/pay-reserved/{order.id}/"),
    }

    # Рендеринг HTML-шаблона письма
    email_html = render_to_string("emails/reservation_payment.html", context)

    # Отправка письма
    sent_count = send_mail(
        subject=f"Бронирование билета #{order.id}",
        message=f"Ваш билет #{order.id} забронирован. Для оплаты перейдите по ссылке: {request.build_absolute_uri(f'/payment/pay-reserved/{order.id}/')}",
        from_email=get_from_email("tickets"),
        recipient_list=[participant_email],
        html_message=email_html,
        fail_silently=False,
    )
    if sent_count != 1:
        raise RuntimeError("Письмо со ссылкой для оплаты не было отправлено.")

def handle_package_change_choice(request):
    """Обработка выбора пользователя при смене пакета."""
    import traceback

    if request.method != "POST":
        return JsonResponse({"error": "Метод не поддерживается"}, status=405)

    try:
        data = json.loads(request.body)
        package_id = data.get("package_id")
        change_type = data.get("change_type")  # "immediate" или "scheduled"
        user = request.user

        if not user.is_authenticated:
            return JsonResponse({"error": "Пользователь не авторизован"}, status=403)

        package = get_object_or_404(EventPackage, id=package_id)
        active_subscription = UserPackageSubscription.objects.filter(
            user=user, is_active=True
        ).first()

        if not active_subscription:
            return JsonResponse({"error": "Активная подписка не найдена"}, status=404)

        if package.pk == active_subscription.package_id:
            return JsonResponse({"error": "Вы уже используете этот пакет"}, status=400)

        if change_type == "immediate":
            # Немедленная смена пакета — создаём заявку в админке.
            # Старая подписка закроется при активации новой.
            new_subscription = UserPackageSubscription.objects.create(
                user=user,
                package=package,
                subscription_type='monthly' if package.is_monthly else 'one_time',
                applicant_name=user.get_full_name() or user.username,
                applicant_phone=user.phone or '',
                applicant_email=user.email,
                is_active=False  # Ждёт оплаты по счёту
            )

            return JsonResponse({
                "status": "success",
                "message": "Заявка на пакет создана. Администратор рассмотрит её в админке.",
                "new_subscription": {
                    "id": new_subscription.id,
                    "package_name": new_subscription.package.name,
                },
            })

        elif change_type == "scheduled":
            # Запланированная смена пакета - планируем изменение на дату окончания текущей подписки
            try:
                active_subscription.schedule_package_change(package)
            except ValidationError as error:
                return JsonResponse({"error": error.message}, status=400)

            return JsonResponse({
                "status": "success",
                "message": "Изменение пакета запланировано",
                "scheduled_change": {
                    "current_package": active_subscription.package.name,
                    "new_package": package.name,
                    "change_date": active_subscription.scheduled_change_date.strftime('%Y-%m-%d %H:%M:%S')
                }
            })

        else:
            return JsonResponse({"error": "Неверный тип изменения"}, status=400)

    except Exception as e:
        logger.error("Ошибка при смене пакета: %s", e, exc_info=True)
        return JsonResponse({"error": str(e)}, status=500)

def create_invoice(request, package_id):
    """
    Создаёт заявку на пакет со статусом ожидания решения администратора.
    Администратор рассматривает и активирует её через админку.
    """
    if request.method != "POST":
        return JsonResponse({"error": "Метод не поддерживается"}, status=405)

    try:
        package = get_object_or_404(EventPackage, id=package_id)
        user = request.user

        if not user.is_authenticated:
            return JsonResponse({"error": "Пользователь не авторизован"}, status=403)

        if not package:
            return JsonResponse({"error": "Пакет не найден"}, status=404)

        # Старую подписку здесь не закрываем: она закроется автоматически
        # в момент активации новой администратором.
        # Если счёт так и не оплатят — текущий пакет продолжит работать.

        # Создаём новую подписку — неактивную, ждём оплату по счёту
        new_subscription = UserPackageSubscription.objects.create(
            user=user,
            package=package,
            subscription_type='monthly' if package.is_monthly else 'one_time',
            applicant_name=request.POST.get('applicant_name', '').strip(),
            applicant_phone=request.POST.get('applicant_phone', '').strip(),
            applicant_email=request.POST.get('applicant_email', '').strip(),
            is_active=False,  # Ждёт оплаты по счёту
        )

        return JsonResponse({
            "status": "success",
            "message": "Заявка на пакет создана. Администратор рассмотрит её в админке.",
            "package_id": package_id,
            "subscription_id": new_subscription.id,
        })

    except Exception as e:
        logger.error("Ошибка при создании счёта: %s", e, exc_info=True)
        return JsonResponse({"error": str(e)}, status=500)


def bulk_buy_tickets(request, event_id):
    """
    API для покупки нескольких типов билетов за один раз.
    При GET-запросе перенаправляет на страницу мероприятия.
    """
    # При GET-запросе перенаправляем на страницу мероприятия с UTM-метками
    if request.method == 'GET':
        event = get_object_or_404(Event, id=event_id)
        utm_params = request.GET.dict()
        if utm_params:
            query_string = '&'.join(f'{k}={v}' for k, v in utm_params.items())
            redirect_url = f'/events/{event_id}/?{query_string}'
        else:
            redirect_url = f'/events/{event_id}/'
        return redirect(redirect_url)

    if request.method != 'POST':
        logger.error('[bulk_buy] Метод не POST', extra={'event_id': event_id})
        return JsonResponse({'error': 'Метод не поддерживается'}, status=405)

    if request.headers.get('X-Requested-With') != 'XMLHttpRequest':
        logger.warning('[bulk_buy] Запрос без AJAX-заголовка отклонён', extra={'event_id': event_id})
        return JsonResponse({'error': 'Invalid request'}, status=403)
    
    try:
        # Парсим JSON тело запроса
        data = json.loads(request.body)
        if not isinstance(data, dict):
            return JsonResponse({'error': 'Неверный формат данных'}, status=400)
        logger.info('[bulk_buy] Получен запрос на покупку', extra={
            'event_id': event_id,
            'tickets': data.get('tickets'),
            'email': data.get('email')
        })
        
        event = get_object_or_404(Event, id=event_id)
        logger.info('[bulk_buy] Мероприятие найдено', extra={'event_title': event.title})
        
        # Получаем данные
        tickets_data = data.get('tickets', [])
        buyer_name = data.get('name', '')
        email = data.get('email', '')
        phone = data.get('phone', '')
        if not all(isinstance(value, str) for value in (buyer_name, email, phone)):
            return JsonResponse({'error': 'Некорректные данные покупателя'}, status=400)
        buyer_name = buyer_name.strip()
        email = email.strip()
        phone = phone.strip()

        # Если имя/телефон не пришли из формы (фронтенд отправляет только email),
        # подтягиваем их из аккаунта пользователя по email.
        if (not buyer_name or not phone) and email:
            from core.models import User as _User
            _user = _User.objects.filter(email=email).first()
            if _user:
                if not buyer_name:
                    buyer_name = _user.get_full_name() or _user.username or ''
                if not phone:
                    phone = getattr(_user, 'phone', '') or ''
        
        # Получаем UTM-метки из JSON (если пришли с фронтенда)
        utm_from_json = data.get('utm_params', {})
        
        # Проверяем бронирование без оплаты.
        # Флаг мероприятия проверяем на сервере: чекбокс на фронте можно не показывать,
        # но подделать POST никто не мешает.
        reserve_without_payment = data.get('reserve_without_payment', False)
        if not isinstance(reserve_without_payment, bool):
            return JsonResponse({'error': 'Некорректный режим бронирования'}, status=400)
        if reserve_without_payment and not event.allow_booking_without_payment:
            logger.warning('[bulk_buy] Бронирование без оплаты запрещено для мероприятия', extra={
                'event_id': event_id,
                'email': email,
            })
            return JsonResponse({
                'error': 'Для этого мероприятия бронирование без оплаты недоступно.'
            }, status=400)
        
        logger.info('[bulk_buy] Данные получены', extra={
            'tickets_count': len(tickets_data) if isinstance(tickets_data, list) else None,
            'buyer_name': buyer_name,
            'email': email,
            'reserve_without_payment': reserve_without_payment
        })
        
        # === ПРОВЕРКА ЛИМИТА БЕЗ СОЗДАНИЯ ЗАКАЗА ===
        if data.get('check_free_limit'):
            if not email:
                return JsonResponse({'error': 'Укажите email'}, status=400)
            try:
                validate_email(email)
            except ValidationError:
                return JsonResponse({'error': 'Укажите корректный email'}, status=400)
            
            event = get_object_or_404(Event, id=event_id)
            already_free = Order.objects.filter(
                participant_data__email=email,
                ticket__event=event,
                ticket__price=0,
                payment_status='succeeded'
            ).aggregate(total=Sum('quantity'))['total'] or 0
            already_free = int(already_free)
            
            if already_free >= 2:
                return JsonResponse({
                    'error': 'Вы уже получили максимальное количество бесплатных билетов (2) на это мероприятие.'
                }, status=400)
            
            return JsonResponse({
                'success': True,
                'already_free': already_free,
                'remaining': 2 - already_free
            })
        
        if not email:
            logger.error('[bulk_buy] Email не указан', extra={'event_id': event_id})
            return JsonResponse({'error': 'Укажите email'}, status=400)
        try:
            validate_email(email)
        except ValidationError:
            return JsonResponse({'error': 'Укажите корректный email'}, status=400)

        if not isinstance(tickets_data, list) or not tickets_data:
            logger.error('[bulk_buy] Корзина пуста или имеет неверный формат', extra={'event_id': event_id})
            return JsonResponse({'error': 'Выберите хотя бы один билет'}, status=400)

        normalized_items = []
        ticket_ids = set()
        for ticket_item in tickets_data:
            if not isinstance(ticket_item, dict):
                return JsonResponse({'error': 'Некорректные данные билетов'}, status=400)
            ticket_id_value = ticket_item.get('id')
            quantity_value = ticket_item.get('quantity')
            valid_ticket_id = (
                type(ticket_id_value) is int
                or isinstance(ticket_id_value, str)
                and ticket_id_value.strip().isdecimal()
            )
            valid_quantity = (
                type(quantity_value) is int
                or isinstance(quantity_value, str)
                and quantity_value.strip().isdecimal()
            )
            if not valid_ticket_id or not valid_quantity:
                return JsonResponse({'error': 'Некорректные данные билетов'}, status=400)
            try:
                ticket_id = int(ticket_id_value)
                quantity = int(quantity_value)
            except (TypeError, ValueError):
                return JsonResponse({'error': 'Некорректные данные билетов'}, status=400)
            if ticket_id <= 0 or quantity <= 0:
                return JsonResponse({'error': 'Количество билетов должно быть больше нуля'}, status=400)
            if ticket_id in ticket_ids:
                return JsonResponse({'error': 'Тип билета указан несколько раз'}, status=400)
            ticket_ids.add(ticket_id)
            normalized_items.append({'id': ticket_id, 'quantity': quantity})

        tickets_by_id = {
            ticket.pk: ticket
            for ticket in Ticket.objects.filter(
                pk__in=ticket_ids,
                event_id=event_id,
            )
        }
        if len(tickets_by_id) != len(ticket_ids):
            return JsonResponse(
                {'error': 'Один или несколько типов билетов не относятся к этому мероприятию'},
                status=400,
            )
        tickets_data = normalized_items
        
        if event.status != "active" or event.date_time <= timezone.now():
            return JsonResponse(
                {'error': 'Продажа билетов на это мероприятие закрыта'},
                status=400,
            )

        # Подсчитываем запрашиваемое количество бесплатных билетов
        requested_free_quantity = 0
        for ticket_item in tickets_data:
            ticket = tickets_by_id[ticket_item['id']]
            if ticket.price == 0:
                requested_free_quantity += ticket_item['quantity']
        
        # === ИЗВЛЕЧЕНИЕ UTM-МЕТОК ИЗ URL И JSON ===
        # Сначала берём из GET (приоритет выше)
        utm_params = {
            "utm_source": request.GET.get("utm_source"),
            "utm_medium": request.GET.get("utm_medium"),
            "utm_campaign": request.GET.get("utm_campaign"),
            "utm_term": request.GET.get("utm_term"),
            "utm_content": request.GET.get("utm_content"),
        }
        
        # Затем дополняем из JSON (если пришли с фронтенда)
        if utm_from_json:
            for key in ["utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content"]:
                if key in utm_from_json and not utm_params.get(key):
                    utm_params[key] = utm_from_json[key]
        
        # Согласия покупателя (152-ФЗ). Для неавторизованных согласие на
        # обработку ПД обязательно; проверяем на сервере, а не только на фронте.
        consent_personal_data = data.get('consent_personal_data') is True
        consent_marketing = data.get('consent_marketing') is True
        if not request.user.is_authenticated and not consent_personal_data:
            return JsonResponse({
                'error': 'Для покупки необходимо согласие на обработку персональных данных.'
            }, status=400)

        # Создаём participant_data
        participant_data = {
            'name': buyer_name,
            'email': email,
            'phone': phone,
            'consent_personal_data': consent_personal_data,
            'consent_marketing': consent_marketing,
        }


        # === РАЗДЕЛЕНИЕ НА БЕСПЛАТНЫЕ И ПЛАТНЫЕ ===
        free_ticket_items = []
        paid_ticket_items = []
        
        for item in tickets_data:
            tid = item['id']
            ticket = tickets_by_id[tid]
            if ticket.price == 0:
                free_ticket_items.append(item)
            else:
                paid_ticket_items.append(item)

        orders = []
        free_orders = []
        
        # === БРОНИРОВАНИЕ БЕСПЛАТНЫХ БИЛЕТОВ (сразу succeeded) ===
        if free_ticket_items:
            try:
                def check_free_ticket_limit():
                    event_free_count = int(
                        Order.objects.filter(
                            participant_data__email=email,
                            ticket__event=event,
                            ticket__price=0,
                            payment_status="succeeded",
                        ).aggregate(total=Sum("quantity"))["total"] or 0
                    )
                    if event_free_count + requested_free_quantity > 2:
                        remaining = max(0, 2 - event_free_count)
                        raise TicketReservationError(
                            f'На это мероприятие можно получить не более 2 бесплатных билетов. '
                            f'У вас уже есть {event_free_count}, можно ещё {remaining}.'
                        )

                free_orders = bulk_reserve_tickets(
                    event_id=event_id,
                    tickets_data=free_ticket_items,
                    participant_data=participant_data,
                    payment_status='succeeded',
                    purchase_type='free_registration',
                    is_paid=True,
                    pre_reservation_check=check_free_ticket_limit,
                    **utm_params,
                )
                orders.extend(free_orders)
                logger.info('[bulk_buy] Бесплатные билеты забронированы', extra={'count': len(free_orders)})
            except TicketReservationError as e:
                logger.error('[bulk_buy] Ошибка бронирования бесплатных: %s', e)
                return JsonResponse({'error': str(e)}, status=400)
        
        # === БРОНИРОВАНИЕ ПЛАТНЫХ БИЛЕТОВ ===
        paid_orders = []
        if paid_ticket_items:
            # Определяем статус платежа
            if reserve_without_payment:
                payment_status = 'reserved'
                purchase_type = 'paid_ticket'
                is_paid = False
                payment_deadline = timezone.now() + timedelta(hours=24)
            else:
                payment_status = 'pending'
                purchase_type = 'paid_ticket'
                is_paid = False
                payment_deadline = None
            
            try:
                def check_reserved_ticket_limit():
                    if not reserve_without_payment:
                        return
                    already_reserved_count = int(
                        Order.objects.filter(
                            participant_data__email=email,
                            ticket__event=event,
                            purchase_type="paid_ticket",
                            payment_status="reserved",
                        ).aggregate(total=Sum("quantity"))["total"] or 0
                    )
                    requested_paid_quantity = sum(
                        item["quantity"] for item in paid_ticket_items
                    )
                    if already_reserved_count + requested_paid_quantity > 3:
                        remaining = max(0, 3 - already_reserved_count)
                        raise TicketReservationError(
                            'На это мероприятие можно забронировать без оплаты не более '
                            f'3 билетов. У вас уже {already_reserved_count}, '
                            f'можно ещё {remaining}.'
                        )

                paid_orders = bulk_reserve_tickets(
                    event_id=event_id,
                    tickets_data=paid_ticket_items,
                    participant_data=participant_data,
                    payment_status=payment_status,
                    purchase_type=purchase_type,
                    is_paid=is_paid,
                    payment_deadline=payment_deadline,
                    pre_reservation_check=check_reserved_ticket_limit,
                    **utm_params,
                )
                orders.extend(paid_orders)
                logger.info('[bulk_buy] Платные билеты забронированы', extra={'count': len(paid_orders), 'reserve_without_payment': reserve_without_payment})
            except TicketReservationError as e:
                # Откатываем бесплатные билеты: удаляем заказы и возвращаем квоту
                for fo in free_orders:
                    Ticket.objects.filter(pk=fo.ticket_id).update(
                        available_quantity=models.F('available_quantity') + fo.quantity
                    )
                    fo.delete()
                logger.error('[bulk_buy] Ошибка бронирования платных: %s', e)
                return JsonResponse({'error': str(e)}, status=400)
        
        # === ОБРАБОТКА БЕСПЛАТНЫХ БИЛЕТОВ ===
        free_email_sent = False
        if free_orders:
            try:
                # Одно письмо на все бесплатные заказы (все типы билетов)
                _send_orders_confirmation_email(free_orders, request)
                Order.objects.filter(
                    pk__in=[free_order.pk for free_order in free_orders]
                ).update(email_sent=True)
                free_email_sent = True
                logger.info('[bulk_buy] Письмо отправлено', extra={'order_ids': [o.id for o in free_orders], 'email': email})
            except Exception as e:
                logger.error('[bulk_buy] Ошибка отправки письма', extra={'order_ids': [o.id for o in free_orders], 'email': email, 'error': str(e)}, exc_info=True)
            
            total_free = Order.objects.filter(
                participant_data__email=email,
                ticket__event=event,
                ticket__price=0,
                payment_status='succeeded'
            ).aggregate(total=Sum('quantity'))['total'] or 0
        
        # === ПЛАТНЫЕ БИЛЕТЫ — СОЗДАНИЕ ПЛАТЕЖА ===
        if not paid_orders:
            # Все билеты бесплатные
            return JsonResponse({
                'success': True,
                'message': (
                    'Билеты успешно оформлены! Проверьте вашу почту.'
                    if free_email_sent
                    else 'Билеты оформлены, но письмо не удалось отправить. Обратитесь в поддержку.'
                ),
                'orders': [o.id for o in free_orders],
                'free_tickets_count': total_free if free_orders else 0
            })
        
        # === БРОНИРОВАНИЕ БЕЗ ОПЛАТЫ ===
        if reserve_without_payment:
            # Не создаём платёж — просто отправляем письмо с бронью
            emailed_paid_orders = []
            failed_reservation_orders = []
            for order in paid_orders:
                try:
                    send_reservation_email(order, request)
                    emailed_paid_orders.append(order)
                    logger.info('[bulk_buy] Письмо с бронью отправлено', extra={'order_id': order.id, 'email': email})
                except Exception:
                    logger.exception(
                        '[bulk_buy] Ошибка отправки письма с бронью',
                        extra={'order_id': order.id, 'email': email},
                    )
                    cancel_unpaid_order(order.pk)
                    failed_reservation_orders.append(order)

            if failed_reservation_orders and not emailed_paid_orders and not free_orders:
                return JsonResponse(
                    {'error': 'Не удалось отправить письмо с оплатой. Бронирование отменено, попробуйте позже.'},
                    status=502,
                )

            order_ids = [o.id for o in free_orders + emailed_paid_orders]
            message = 'Билеты успешно забронированы! Проверьте вашу почту для оплаты.'
            if failed_reservation_orders:
                message = (
                    'Часть платных билетов не удалось забронировать и она отменена. '
                    'Для остальных проверьте почту; бесплатные билеты оформлены.'
                )
            
            return JsonResponse({
                'success': True,
                'message': message,
                'order_ids': order_ids,
                'order_id': emailed_paid_orders[0].id if emailed_paid_orders else (free_orders[0].id if free_orders else None),
                'free_tickets_count': total_free if free_orders else 0
            })
        
        # Платные билеты - создаём платёж
        logger.info('[bulk_buy] Создание платежа Робокасса', extra={'orders_count': len(paid_orders)})
        
        combined_total = sum(o.total_price for o in paid_orders)
        try:
            payment, payment_url = _create_robokassa_payment(
                paid_orders,
                combined_total,
                f"Билеты на мероприятие {event.title}",
                email,
            )
        except Exception:
            logger.exception(
                '[bulk_buy] Не удалось создать Robokassa-платёж для заказов %s',
                [order.pk for order in paid_orders],
            )
            for paid_order in paid_orders:
                cancel_unpaid_order(paid_order.pk)
            if free_orders:
                return JsonResponse({
                    'success': True,
                    'message': (
                        'Бесплатные билеты оформлены, но платный заказ не удалось создать. '
                        'Бронь платных билетов отменена.'
                    ),
                    'order_ids': [order.pk for order in free_orders],
                    'free_tickets_count': total_free,
                })
            return JsonResponse(
                {'error': 'Не удалось создать счёт. Бронь отменена, попробуйте позже.'},
                status=502,
            )
        
        logger.info('[bulk_buy] Платёж создан успешно', extra={
            'payment_id': payment.pk,
            'orders_count': len(paid_orders)
        })
        
        return JsonResponse({
            'success': True,
            'payment_url': payment_url,
            'order_ids': [o.id for o in orders],
            'order_id': paid_orders[0].id if paid_orders else (free_orders[0].id if free_orders else None),
            'free_tickets_count': total_free if free_orders else 0
        })
        
    except json.JSONDecodeError:
        logger.error('[bulk_buy] Неверный JSON в запросе', extra={'event_id': event_id})
        return JsonResponse({'error': 'Неверный формат данных'}, status=400)
    
    except Exception as e:
        logger.error('[bulk_buy] Критическая ошибка', extra={
            'event_id': event_id,
            'error': str(e)
        }, exc_info=True)
        return JsonResponse({'error': str(e)}, status=500)


def _buy_ticket_error(request, ticket, message):
    """
    Единый формат ошибки для create_payment.
    Форма всегда отправляется AJAX-ом (buy_ticket.js) — отдаём JSON,
    чтобы фронтенд показал сообщение. HTML-рендер — фолбэк для не-AJAX.
    """
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return JsonResponse({"error": message}, status=400)
    return render(
        request,
        "payment/buy_ticket.html",
        {"ticket": ticket, "error_message": message},
    )


@require_POST
def create_payment(request, ticket_id):
    """
    Создание платежа в Робокассе для покупки билета или бронирование без оплаты.
    Использует атомарное бронирование с двойной защитой от гонки (Redis + SELECT FOR UPDATE).
    """
    try:
        ticket = get_object_or_404(Ticket, id=ticket_id)

        # Данные участника из формы
        participant_data = {
            "name": request.POST.get("name", "").strip(),
            "email": request.POST.get("email", "").strip(),
            "phone": request.POST.get("phone", "").strip(),
        }
        if not all(participant_data.values()):
            return _buy_ticket_error(
                request, ticket, "Заполните имя, email и телефон."
            )
        try:
            validate_email(participant_data["email"])
        except ValidationError:
            return _buy_ticket_error(request, ticket, "Укажите корректный email.")

        # Согласия покупателя (152-ФЗ). Для неавторизованных согласие на
        # обработку ПД обязательно, проверяем на сервере.
        consent_personal_data = request.POST.get("consent_personal_data") == "on"
        consent_marketing = request.POST.get("consent_marketing") == "on"
        participant_data["consent_personal_data"] = consent_personal_data
        participant_data["consent_marketing"] = consent_marketing
        if not request.user.is_authenticated and not consent_personal_data:
            return _buy_ticket_error(
                request, ticket,
                "Необходимо согласие на обработку персональных данных.",
            )


        # Проверка, выбран ли чекбокс "Заявка организатору"
        request_to_organizer = request.POST.get("request_to_organizer") == "on"
        if request_to_organizer:
            # Обработка заявки организатору
            from core.models import SupportTicket, SupportMessage, User

            # Проверка обязательных полей
            if not all(
                participant_data.get(field)
                for field in ("name", "email", "phone")
            ):
                from django.shortcuts import render
                return render(
                    request,
                    "payment/buy_ticket.html",
                    {
                        "ticket": ticket,
                        "error_message": "Все поля обязательны для заполнения."
                    },
                )

            # Создаём или получаем пользователя
            # Проверяем, не принадлежит ли email зарегистрированному пользователю
            existing_user = User.objects.filter(email=participant_data["email"]).first()
            if existing_user:
                user = existing_user
                if user.user_type == "guest":
                    name_parts = participant_data["name"].strip().split()
                    user.first_name = name_parts[0]
                    user.last_name = " ".join(name_parts[1:])
                    user.save(update_fields=["first_name", "last_name"])
            else:
                # Создаём guest-аккаунт для email, которого ещё нет на платформе
                name_parts = participant_data["name"].strip().split()
                user, created = User.objects.get_or_create(
                    username=participant_data["email"],
                    defaults={
                        "email": participant_data["email"],
                        "first_name": name_parts[0],
                        "last_name": " ".join(name_parts[1:]),
                        "user_type": "guest",
                    },
                )
                if created:
                    user.set_unusable_password()
                    user.save()

            # Создаём тикет
            support_ticket = SupportTicket.objects.create(
                user=user,
                subject=f"Заявка на мероприятие: {ticket.event.title}",
                event=ticket.event,
            )

            # Создаём сообщение с вопросом организатору
            organizer_question = request.POST.get("organizer_question", "")
            SupportMessage.objects.create(
                ticket=support_ticket,
                user=user,
                is_from_user=True,
                text=f"{organizer_question}",
            )

            return JsonResponse(
                {
                    "success": True,
                    "redirect_url": "/",
                    "message": "Ваша заявка отправлена организатору!",
                }
            )

        try:
            quantity = int(request.POST.get("quantity", 1))
        except (TypeError, ValueError):
            return _buy_ticket_error(request, ticket, "Некорректное количество билетов.")
        if quantity <= 0:
            return _buy_ticket_error(request, ticket, "Количество билетов должно быть больше нуля.")
        
        # === ИЗВЛЕЧЕНИЕ UTM-МЕТОК ИЗ URL ===
        utm_params = {
            "utm_source": request.GET.get("utm_source"),
            "utm_medium": request.GET.get("utm_medium"),
            "utm_campaign": request.GET.get("utm_campaign"),
            "utm_term": request.GET.get("utm_term"),
            "utm_content": request.GET.get("utm_content"),
        }

        # Проверка лимита бесплатных билетов за один заказ
        if ticket.price == 0 and quantity > 2:
            return _buy_ticket_error(
                request, ticket,
                "За один заказ можно получить не более 2 бесплатных билетов."
            )
        # Проверка, выбран ли чекбокс "Забронировать без оплаты".
        # Флаг мероприятия проверяем на сервере — POST можно подделать.
        reserve_without_payment = request.POST.get("reserve_without_payment") == "on"
        if reserve_without_payment and not ticket.event.allow_booking_without_payment:
            return _buy_ticket_error(
                request, ticket,
                "Для этого мероприятия бронирование без оплаты недоступно."
            )

        # Определяем статус платежа
        if ticket.price == 0:
            payment_status = "succeeded"
            purchase_type = "free_registration"
            is_paid = True
            payment_deadline = None
        elif reserve_without_payment:
            payment_status = "reserved"
            purchase_type = "paid_ticket"
            is_paid = False
            payment_deadline = timezone.now() + timedelta(hours=24)
        else:
            payment_status = "pending"
            purchase_type = "paid_ticket"
            is_paid = False
            payment_deadline = timezone.now() + timedelta(hours=10)

        total_price = ticket.price * quantity

        MAX_RESERVED_TICKETS_PER_EVENT = 3

        # === АТОМАРНОЕ БРОНИРОВАНИЕ С ЗАЩИТОЙ ОТ ГОНКИ ===
        try:
            def check_single_purchase_limits():
                if payment_status == "reserved":
                    already_reserved_count = int(
                        Order.objects.filter(
                            participant_data__email=participant_data["email"],
                            ticket__event=ticket.event,
                            purchase_type="paid_ticket",
                            payment_status="reserved",
                        ).aggregate(total=Sum("quantity"))["total"] or 0
                    )
                    if already_reserved_count + quantity > MAX_RESERVED_TICKETS_PER_EVENT:
                        remaining = max(0, MAX_RESERVED_TICKETS_PER_EVENT - already_reserved_count)
                        raise TicketReservationError(
                            f"На это мероприятие можно забронировать без оплаты не более "
                            f"{MAX_RESERVED_TICKETS_PER_EVENT} билетов. "
                            f"У вас уже {already_reserved_count}, можно ещё {remaining}."
                        )

                if ticket.price == 0:
                    free_tickets_count = int(
                        Order.objects.filter(
                            participant_data__email=participant_data["email"],
                            ticket__event=ticket.event,
                            ticket__price=0,
                            payment_status="succeeded",
                        ).aggregate(total=Sum("quantity"))["total"] or 0
                    )
                    if free_tickets_count + quantity > 2:
                        raise TicketReservationError(
                            f"На это мероприятие можно получить не более 2 бесплатных билетов. "
                            f"У вас уже {free_tickets_count}, можно ещё "
                            f"{max(0, 2 - free_tickets_count)}."
                        )

            order = reserve_tickets(
                ticket_id=ticket_id,
                quantity=quantity,
                participant_data=participant_data,
                total_price=total_price,
                payment_status=payment_status,
                purchase_type=purchase_type,
                is_paid=is_paid,
                payment_deadline=payment_deadline,
                pre_reservation_check=check_single_purchase_limits,
                **utm_params,
            )
        except TicketReservationError as e:
            logger.warning("[create_payment] Ошибка бронирования: %s", e)
            return _buy_ticket_error(request, ticket, str(e))

        # Отправка писем для бесплатных билетов
        if ticket.price == 0:
            try:
                send_order_confirmation_email(order, request)
            except Exception:
                logger.exception(
                    "[create_payment] Не удалось отправить письмо для заказа #%s",
                    order.pk,
                )
            else:
                order.email_sent = True
                order.save(update_fields=["email_sent"])
            return redirect(f"/payment/success/{order.id}/")

        if reserve_without_payment:
            try:
                send_reservation_email(order, request)
            except Exception:
                logger.exception(
                    "[create_payment] Не удалось отправить ссылку для брони #%s",
                    order.pk,
                )
                cancel_unpaid_order(order.pk)
                return _buy_ticket_error(
                    request,
                    ticket,
                    "Не удалось отправить письмо с оплатой. Бронирование отменено, попробуйте позже.",
                )
            return redirect(f"/payment/success/{order.id}/")

        # Создание платежа в Робокассе для платных билетов
        try:
            payment, payment_url = _create_robokassa_payment(
                [order],
                order.total_price,
                f"Билет на мероприятие {ticket.event.title}",
                participant_data["email"],
            )
        except Exception:
            logger.exception(
                "[create_payment] Не удалось создать платёж для заказа #%s",
                order.pk,
            )
            cancel_unpaid_order(order.pk)
            return _buy_ticket_error(
                request,
                ticket,
                "Не удалось создать счёт. Бронь отменена, попробуйте позже.",
            )

        return JsonResponse(
            {
                "payment_url": payment_url,
                "order_id": order.id,
            }
        )

    except Exception as e:
        logger.error("Ошибка при создании платежа: %s", e, exc_info=True)
        return JsonResponse({"error": str(e)}, status=500)


@login_required
@require_POST
def refund_ticket(request, order_id, order_ticket_id=None):
    """
    Возврат билета.
    Для бесплатных билетов — просто обновляем статус в БД.
    Платные возвраты оформляются через API Робокассы.
    
    Если передан order_ticket_id — возвращаем только один билет из заказа.
    """
    try:
        logger.info("[refund] Начало возврата: order_id=%s, order_ticket_id=%s", order_id, order_ticket_id)
        order = get_object_or_404(Order, id=order_id)
        refund_all_payment = request.POST.get("refund_scope") == "whole_payment"
        participant_email = (order.participant_data or {}).get("email", "")
        if not participant_email or participant_email.casefold() != (request.user.email or "").casefold():
            return HttpResponseForbidden("Возврат этого заказа недоступен.")
        logger.info(
            "[refund] Заказ найден: id=%s, status=%s, payment_id=%s, price=%s, quantity=%s",
            order.id, order.payment_status, order.payment_id, order.total_price, order.quantity
        )

        if order.payment_status != "succeeded" or not order.is_paid:
            return render(
                request,
                "/payment/refund_error.html",
                {"error": "Заказ не оплачен или билет не был оплачен"},
            )

        # === ДЛЯ БЕСПЛАТНЫХ БИЛЕТОВ — ВОЗВРАТ БЕЗ ПРОВАЙДЕРА ===
        if float(order.total_price) == 0:
            logger.info("[refund] Бесплатный билет: возврат в БД для order_id=%s", order.id)
            with transaction.atomic():
                order = Order.objects.select_for_update().get(pk=order.pk)
                ticket = Ticket.objects.select_for_update().get(pk=order.ticket_id)
                tickets = list(
                    OrderTicket.objects.select_for_update()
                    .filter(order=order)
                    .order_by("ticket_number")
                )
                if order_ticket_id and not refund_all_payment:
                    ticket_to_refund = next(
                        (item for item in tickets if item.pk == order_ticket_id),
                        None,
                    )
                    if ticket_to_refund is None:
                        raise Http404("Билет заказа не найден")
                    if ticket_to_refund.is_refunded or ticket_to_refund.attended:
                        return render(
                            request,
                            "payment/refund_error.html",
                            {"error": "Этот билет уже возвращён или использован."},
                            status=400,
                        )
                    ticket_to_refund.is_refunded = True
                    ticket_to_refund.save(update_fields=["is_refunded"])
                    ticket.available_quantity += 1
                    ticket.save(update_fields=["available_quantity"])
                    if not order.tickets.filter(is_refunded=False).exists():
                        order.payment_status = "refunded"
                        order.save(update_fields=["payment_status"])
                else:
                    if any(item.attended for item in tickets):
                        return render(
                            request,
                            "payment/refund_error.html",
                            {"error": "Нельзя вернуть уже использованный билет."},
                            status=400,
                        )
                    active_tickets = [
                        item for item in tickets if not item.is_refunded
                    ]
                    for item in active_tickets:
                        item.is_refunded = True
                        item.save(update_fields=["is_refunded"])
                    ticket.available_quantity += len(active_tickets) or order.quantity
                    ticket.save(update_fields=["available_quantity"])
                    order.payment_status = "refunded"
                    order.save(update_fields=["payment_status"])
            if order_ticket_id and not refund_all_payment:
                logger.info(
                    "[refund] Бесплатный билет заказа #%s помечен как возвращённый",
                    order.id,
                )
            else:
                logger.info("[refund] Бесплатный заказ #%s помечен как возвращённый", order.id)

            return render(request, "payment/refund_success_free.html")

        # === ДЛЯ ПЛАТНЫХ БИЛЕТОВ ===
        if not order.payment_id:
            return render(
                request,
                "payment/refund_error.html",
                {"error": "У заказа отсутствует идентификатор платежа Робокассы."},
                status=400,
            )
        if settings.ROBOKASSA_TEST_MODE:
            return render(
                request,
                "payment/refund_error.html",
                {
                    "error": (
                        "Возврат тестового платежа через API Robokassa недоступен. "
                        "Проверка операции и получение ключа возврата работают "
                        "только для реальных платежей."
                    )
                },
                status=400,
            )

        with transaction.atomic():
            payment = RobokassaPayment.objects.select_for_update().get(
                pk=int(order.payment_id)
            )
            payment_orders = list(
                payment.orders.select_for_update()
                .select_related("ticket__event")
                .order_by("id")
            )
            if not payment_orders:
                return render(
                    request,
                    "payment/refund_error.html",
                    {"error": "В платеже не найдены связанные заказы."},
                    status=400,
                )
            order = next(
                (payment_order for payment_order in payment_orders if payment_order.pk == order.pk),
                None,
            )
            if order is None:
                return render(
                    request,
                    "payment/refund_error.html",
                    {"error": "Заказ не связан с этим платежом."},
                    status=409,
                )

            all_payment_orders = payment_orders
            if refund_all_payment:
                for payment_order in payment_orders:
                    email = (payment_order.participant_data or {}).get("email", "")
                    if (email or "").casefold() != (request.user.email or "").casefold():
                        return HttpResponseForbidden(
                            "Возврат всей покупки недоступен."
                        )
                    if payment_order.payment_status != "succeeded" or not payment_order.is_paid:
                        return render(
                            request,
                            "payment/refund_error.html",
                            {"error": "Не все заказы этой покупки подтверждены как оплаченные."},
                            status=409,
                        )
            else:
                payment_orders = [order]

            tickets_by_order = {
                payment_order.pk: list(
                    OrderTicket.objects.select_for_update()
                    .filter(order=payment_order)
                    .order_by("ticket_number")
                )
                for payment_order in payment_orders
            }
            tickets = tickets_by_order[order.pk]
            if order_ticket_id and not refund_all_payment:
                ticket_to_refund = next(
                    (ticket for ticket in tickets if ticket.pk == order_ticket_id),
                    None,
                )
                if ticket_to_refund is None:
                    raise Http404("Билет заказа не найден")
                if ticket_to_refund.is_refunded or ticket_to_refund.attended:
                    return render(
                        request,
                        "payment/refund_error.html",
                        {"error": "Этот билет уже возвращён или использован."},
                        status=400,
                    )
            elif not refund_all_payment and any(
                ticket.is_refunded or ticket.attended for ticket in tickets
            ):
                return render(
                    request,
                    "payment/refund_error.html",
                    {
                        "error": (
                            "В заказе уже возвращён или использован отдельный билет. "
                            "Оставшиеся билеты верните по одному."
                        )
                    },
                    status=400,
                )

            receipt_data = payment.receipt_data or {}
            order_items = receipt_data.get("order_items") or {}
            if not settings.ROBOKASSA_PASSWORD3:
                return render(
                    request,
                    "payment/refund_error.html",
                    {"error": "Для возвратов не настроен пароль Robokassa №3."},
                    status=503,
                )

            payment_refunds = RobokassaRefund.objects.filter(
                models.Q(order__in=all_payment_orders)
                | models.Q(orders__in=all_payment_orders)
            ).exclude(status__in=["failed", "canceled"]).distinct()
            prior_payment_amount = (
                payment_refunds.aggregate(total=Sum("amount"))["total"]
                or Decimal("0")
            )
            payment_remaining_amount = payment.amount - prior_payment_amount

            if refund_all_payment:
                if payment_refunds.exclude(status="succeeded").exists():
                    return render(
                        request,
                        "payment/refund_error.html",
                        {"error": "По этой покупке уже есть возврат в обработке."},
                        status=409,
                    )
                refund_items = []
                refund_amount = Decimal("0.00")
                for payment_order in payment_orders:
                    original_item = order_items.get(str(payment_order.pk))
                    if not original_item:
                        return render(
                            request,
                            "payment/refund_error.html",
                            {
                                "error": (
                                    "В сохранённом чеке отсутствуют данные одного из заказов. "
                                    "Обратитесь в поддержку."
                                )
                            },
                            status=400,
                        )
                    order_tickets = tickets_by_order[payment_order.pk]
                    active_tickets = [
                        ticket for ticket in order_tickets if not ticket.is_refunded
                    ]
                    if any(ticket.attended for ticket in active_tickets):
                        return render(
                            request,
                            "payment/refund_error.html",
                            {"error": "Нельзя вернуть уже использованный билет."},
                            status=400,
                        )
                    quantity_to_refund = (
                        len(active_tickets) if order_tickets else payment_order.quantity
                    )
                    if quantity_to_refund <= 0:
                        continue
                    item_cost = Decimal(str(original_item["cost"])).quantize(
                        Decimal("0.01")
                    )
                    refund_amount += item_cost * quantity_to_refund
                    refund_items.append({
                        "Name": original_item["name"],
                        "Quantity": quantity_to_refund,
                        "Cost": float(item_cost),
                        "Tax": original_item["tax"],
                        "PaymentMethod": original_item["payment_method"],
                        "PaymentObject": original_item["payment_object"],
                    })
                refund_amount = refund_amount.quantize(Decimal("0.01"))
                if refund_amount <= 0 or refund_amount != payment_remaining_amount:
                    return render(
                        request,
                        "payment/refund_error.html",
                        {
                            "error": (
                                "Сумма оставшихся билетов не совпадает с остатком платежа. "
                                "Обратитесь в поддержку."
                            )
                        },
                        status=409,
                    )
                is_full_refund = refund_amount == payment.amount
                refund_order_ticket_id = None
            else:
                original_item = order_items.get(str(order.pk))
                if not original_item:
                    return render(
                        request,
                        "payment/refund_error.html",
                        {
                            "error": (
                                "Для этого старого платежа нет сохранённых данных чека. "
                                "Автоматический возврат недоступен; обратитесь в поддержку."
                            )
                        },
                        status=400,
                    )
                order_refunds = RobokassaRefund.objects.filter(
                    models.Q(order=order) | models.Q(orders=order)
                ).exclude(status__in=["failed", "canceled"]).distinct()
                if not order_ticket_id and order_refunds.exists():
                    return render(
                        request,
                        "payment/refund_error.html",
                        {"error": "По этому заказу уже есть незавершённый или выполненный возврат."},
                        status=409,
                    )
                if order_ticket_id and order_refunds.filter(
                    order_ticket_id=order_ticket_id
                ).exists():
                    return render(
                        request,
                        "payment/refund_error.html",
                        {"error": "Возврат этого билета уже запрошен или выполнен."},
                        status=409,
                    )
                prior_amount = (
                    order_refunds.aggregate(total=Sum("amount"))["total"]
                    or Decimal("0")
                )
                remaining_amount = order.total_price - prior_amount
                item_cost = Decimal(str(original_item["cost"])).quantize(
                    Decimal("0.01")
                )
                quantity_to_refund = (
                    1 if order_ticket_id
                    else order.quantity - sum(ticket.is_refunded for ticket in tickets)
                )
                refund_amount = min(
                    item_cost * quantity_to_refund,
                    remaining_amount,
                    payment_remaining_amount,
                ).quantize(Decimal("0.01"))
                if refund_amount <= 0 or quantity_to_refund <= 0:
                    return render(
                        request,
                        "payment/refund_error.html",
                        {"error": "Для возврата не осталось оплаченной суммы."},
                        status=400,
                    )
                if refund_amount != item_cost * quantity_to_refund:
                    return render(
                        request,
                        "payment/refund_error.html",
                        {
                            "error": (
                                "Сумма оставшегося платежа не совпадает с суммой билета. "
                                "Обратитесь в поддержку."
                            )
                        },
                        status=409,
                    )
                refund_items = [{
                    "Name": original_item["name"],
                    "Quantity": quantity_to_refund,
                    "Cost": float(item_cost),
                    "Tax": original_item["tax"],
                    "PaymentMethod": original_item["payment_method"],
                    "PaymentObject": original_item["payment_object"],
                }]
                is_full_refund = (
                    refund_amount == payment.amount
                    and len(payment_orders) == 1
                    and quantity_to_refund == order.quantity
                )
                refund_order_ticket_id = order_ticket_id

            refund = RobokassaRefund.objects.create(
                order=order,
                order_ticket_id=refund_order_ticket_id,
                amount=refund_amount,
                status="requesting",
            )
            refund.orders.set(payment_orders)
            operation_key = (
                payment.operation_key
                or (payment.notification_data or {}).get("OpKey")
                or (payment.notification_data or {}).get("OperationKey")
            )
            invoice_id = payment.pk

        if not operation_key:
            try:
                operation = get_operation_details(invoice_id)
                if operation["state"] != 100:
                    raise RuntimeError(
                        "Robokassa не подтверждает успешную оплату по этому счёту."
                    )
                operation_key = operation["op_key"]
                RobokassaPayment.objects.filter(pk=invoice_id).update(
                    operation_key=operation_key
                )
            except Exception as exc:
                logger.exception(
                    "[refund] Не удалось подтвердить оплату InvId=%s через Robokassa",
                    invoice_id,
                )
                refund.status = "failed"
                refund.response_data = {"error": str(exc)}
                refund.save(update_fields=["status", "response_data", "updated_at"])
                return render(
                    request,
                    "payment/refund_error.html",
                    {"error": "Не удалось подтвердить исходную оплату в Robokassa."},
                    status=502,
                )

        try:
            result = create_refund(
                operation_key,
                refund.amount,
                refund_items,
                full_refund=is_full_refund,
            )
        except RefundRejectedError as exc:
            refund.status = "failed"
            refund.response_data = {"error": str(exc)}
            refund.save(update_fields=["status", "response_data", "updated_at"])
            return render(
                request,
                "payment/refund_error.html",
                {"error": str(exc)},
                status=400,
            )
        except Exception:
            logger.exception("[refund] Неизвестен результат запроса Robokassa")
            refund.status = "unknown"
            refund.save(update_fields=["status", "updated_at"])
            return render(
                request,
                "payment/refund_error.html",
                {
                    "error": (
                        "Не удалось подтвердить, создан ли возврат в Robokassa. "
                        "Не отправляйте запрос повторно; обратитесь в поддержку."
                    )
                },
                status=502,
            )

        refund.request_id = result["requestId"]
        refund.status = "processing"
        refund.response_data = result
        refund.save(
            update_fields=["request_id", "status", "response_data", "updated_at"]
        )
        return render(
            request,
            "payment/refund_requested.html",
            {"refund": refund},
            status=202,
        )

    except Exception as e:
        logger.error("Ошибка при возврате заказа: %s", e, exc_info=True)
        return render(request, "payment/refund_error.html", {"error": str(e)})


def payment_success(request, order_id):
    """
    Страница успешной оплаты.
    Статус платежа подтверждается серверным уведомлением провайдера.
    """
    order = get_object_or_404(Order, id=order_id)
    orders = [order]
    payment_amount = order.total_price

    if order.payment_id:
        try:
            payment = RobokassaPayment.objects.get(pk=int(order.payment_id))
            payment_orders = list(
                payment.orders.select_related("ticket__event").order_by("id")
            )
            if payment_orders:
                orders = payment_orders
                order = next(
                    (payment_order for payment_order in orders if payment_order.pk == order.pk),
                    orders[0],
                )
                payment_amount = payment.amount
        except (RobokassaPayment.DoesNotExist, ValueError):
            logger.warning(
                "[success] Не найдена попытка Робокассы для заказа #%s",
                order.id,
            )
    all_paid = all(
        paid_order.payment_status == "succeeded" and paid_order.is_paid
        for paid_order in orders
    )
    all_refunded = all(
        paid_order.payment_status == "refunded"
        for paid_order in orders
    )
    return render(
        request,
        "payment/payment_success.html",
        {
            "order": order,
            "orders": orders,
            "payment_amount": payment_amount,
            "payment_failed": request.GET.get("payment_failed") == "1",
            "all_paid": all_paid,
            "all_refunded": all_refunded,
            "has_reserved": any(
                paid_order.payment_status == "reserved" for paid_order in orders
            ),
            "confirmation_email_sent": all(
                paid_order.email_sent for paid_order in orders
            ),
        },
    )

@login_required
def pay_reserved_order(request, order_id):
    """
    Оплата забронированного билета.
    """
    try:
        with transaction.atomic():
            order = get_object_or_404(
                Order.objects.select_for_update(),
                id=order_id,
            )
            participant_email = (order.participant_data or {}).get("email", "")
            if (
                not participant_email
                or participant_email.casefold()
                != (request.user.email or "").casefold()
            ):
                return HttpResponseForbidden("Оплата этого заказа недоступна.")

            if order.payment_status not in ["reserved", "pending"]:
                return render(
                    request,
                    "payment/refund_error.html",
                    {"error": "Этот заказ не может быть оплачен"},
                )

            now = timezone.now()
            if (
                order.payment_status == "reserved"
                and order.payment_deadline
                and now >= order.payment_deadline
            ):
                return render(
                    request,
                    "payment/refund_error.html",
                    {"error": "Срок бронирования истёк. Создайте новый заказ."},
                    status=400,
                )

            if order.payment_status == "pending" and order.payment_id:
                try:
                    payment = RobokassaPayment.objects.get(pk=int(order.payment_id))
                except (RobokassaPayment.DoesNotExist, ValueError):
                    logger.warning(
                        "[pay_reserved] Попытка Робокассы не найдена для заказа #%s",
                        order.id,
                    )
                else:
                    payment_expiration = payment.created_at + timedelta(minutes=15)
                    if payment.status == "succeeded":
                        return redirect("payment:payment_success", order_id=order.id)
                    if payment.status == "pending" and now < payment_expiration:
                        return redirect(
                            build_payment_url(
                                payment.pk,
                                payment.amount,
                                f"Билет на мероприятие {order.ticket.event.title}",
                                email=participant_email,
                                receipt=(payment.receipt_data or {}).get("receipt"),
                                expiration_date=payment_expiration,
                            )
                        )
                    if payment.status == "pending":
                        return render(
                            request,
                            "payment/refund_error.html",
                            {"error": "Срок оплаты истёк. Создайте новый заказ для покупки билета."},
                            status=400,
                        )

            payment, payment_url = _create_robokassa_payment(
                [order],
                order.total_price,
                f"Билет на мероприятие {order.ticket.event.title}",
                participant_email,
            )

            order.payment_status = "pending"
            order.save(update_fields=["payment_status"])

        return redirect(payment_url)

    except Exception as e:
        logger.error("Ошибка при оплате забронированного заказа: %s", e, exc_info=True)
        return render(request, "payment/refund_error.html", {"error": str(e)})


@csrf_exempt
def robokassa_result(request):
    """Проверяет подпись и регистрирует подтверждённый платёж Робокассы."""
    if request.method not in ("GET", "POST"):
        return HttpResponse("Method not allowed", status=405)

    params = request.GET.copy()
    params.update(request.POST)
    inv_id = params.get("InvId") or params.get("InvoiceID")
    out_sum = params.get("OutSum")
    if not inv_id or not out_sum or not verify_result_signature(params):
        logger.warning("[robokassa] Некорректная подпись или параметры callback")
        return HttpResponse("Invalid signature or parameters", status=400)

    try:
        inv_id = int(inv_id)
        received_amount = Decimal(out_sum)
        with transaction.atomic():
            payment = RobokassaPayment.objects.select_for_update().get(pk=inv_id)
            if received_amount != payment.amount:
                logger.error(
                    "[robokassa] Сумма callback не совпала: InvId=%s, received=%s, expected=%s",
                    inv_id,
                    received_amount,
                    payment.amount,
                )
                return HttpResponse("Invalid amount", status=400)
            if payment.status == "succeeded":
                return HttpResponse(f"OK{inv_id}", content_type="text/plain")
            if payment.status == "canceled":
                logger.warning(
                    "[robokassa] Отклонён callback по отменённому счёту InvId=%s",
                    inv_id,
                )
                return HttpResponse("Invoice canceled", status=409)

            orders = list(
                payment.orders.select_for_update()
                .select_related("ticket__event")
                .order_by("id")
            )
            if not orders:
                logger.error("[robokassa] Для InvId=%s нет связанных заказов", inv_id)
                return HttpResponse("Unknown invoice", status=404)

            payment.status = "succeeded"
            payment.notification_data = params.dict()
            payment.operation_key = params.get("OpKey") or params.get("OperationKey")
            payment.save(
                update_fields=[
                    "status",
                    "notification_data",
                    "operation_key",
                    "updated_at",
                ]
            )
            for order in orders:
                order.payment_status = "succeeded"
                order.is_paid = True
                order.save(update_fields=["payment_status", "is_paid"])

            pending_email_orders = [order for order in orders if not order.email_sent]

            def _after_payment():
                if pending_email_orders:
                    try:
                        _send_orders_confirmation_email(pending_email_orders, request)
                        Order.objects.filter(
                            id__in=[order.id for order in pending_email_orders]
                        ).update(email_sent=True)
                    except Exception:
                        logger.exception(
                            "[robokassa] Ошибка отправки письма для InvId=%s",
                            inv_id,
                        )

            transaction.on_commit(_after_payment)

        return HttpResponse(f"OK{inv_id}", content_type="text/plain")
    except RobokassaPayment.DoesNotExist:
        logger.error("[robokassa] Неизвестный InvId=%s", inv_id)
        return HttpResponse("Unknown invoice", status=404)
    except (InvalidOperation, ValueError, TypeError):
        return HttpResponse("Invalid payment data", status=400)
    except Exception:
        logger.exception("[robokassa] Ошибка обработки callback InvId=%s", inv_id)
        return HttpResponse("Payment processing failed", status=500)


def _robokassa_return(request, payment_failed=False):
    params = request.GET.copy()
    params.update(request.POST)
    inv_id = params.get("InvId") or params.get("InvoiceID")
    try:
        payment = RobokassaPayment.objects.get(pk=int(inv_id))
        order = payment.orders.order_by("id").first()
    except (RobokassaPayment.DoesNotExist, TypeError, ValueError):
        raise Http404("Robokassa invoice not found")
    if order is None:
        raise Http404("Order for Robokassa invoice not found")
    success_url = reverse("payment:payment_success", args=[order.id])
    if payment_failed and payment.status != "succeeded":
        success_url = f"{success_url}?payment_failed=1"
    return redirect(success_url)


def robokassa_success(request):
    """Возвращает покупателя на страницу статуса заказа после оплаты."""
    return _robokassa_return(request)


def robokassa_fail(request):
    """Возвращает покупателя на страницу статуса заказа после отказа от оплаты."""
    return _robokassa_return(request, payment_failed=True)
