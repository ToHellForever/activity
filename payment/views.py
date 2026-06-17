from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponse, Http404
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from django.utils import timezone
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from core.models import Order, Ticket, Event, EventPackage, UserPackageSubscription, CustomUser
from django.db import transaction, models
from django.db.models import Sum, F
import json
import uuid
from yookassa import Configuration, Payment
# timedelta
from datetime import timedelta
# Настройка ЮКассы
Configuration.account_id = settings.YOOKASSA_SHOP_ID
Configuration.secret_key = settings.YOOKASSA_SECRET_KEY

# Логгер для покупки билетов
import logging
logger = logging.getLogger('ticket_purchase')


def send_order_confirmation_email(order, request=None):
    """
    Отправка уведомления на почту с информацией о заказе.
    QR-коды генерируются на лету и вставляются как base64 в письмо.
    """
    participant_email = order.participant_data.get("email")
    if not participant_email:
        logger.warning('[email] Email участника пуст для заказа %s', order.id)
        return

    from django.core.mail import EmailMultiAlternatives
    from django.conf import settings

    # Генерируем QR-коды "на лету"
    qr_codes = order.generate_qr_data()
    logger.info('[email] QR-коды сгенерированы для заказа %s, count=%d', order.id, len(qr_codes))

    context = {
        "order": order,
        "ticket": order.ticket,
        "participant_data": order.participant_data,
        "qr_codes": qr_codes,
    }

    email_html = render_to_string("emails/ticket_confirmation.html", context)

    email_message = EmailMultiAlternatives(
        subject=f"Подтверждение заказа #{order.id}",
        body=f"Ваш заказ #{order.id} успешно оплачен.",
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[participant_email],
    )
    email_message.attach_alternative(email_html, "text/html")

    email_message.send(fail_silently=False)
    logger.info('[email] Письмо отправлено для заказа %s на %s', order.id, participant_email)


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

def send_package_purchase_email(subscription, request=None):
    """
    Отправка уведомления на почту с информацией о покупке пакета.
    """
    user_email = subscription.user.email
    if not user_email:
        return

    # Формирование контекста для шаблона письма
    context = {
        "subscription": subscription,
        "package": subscription.package,
        "user": subscription.user,
        "request": request,
    }

    # Рендеринг HTML-шаблона письма
    email_html = render_to_string("emails/package_purchase_confirmation.html", context)

    # Отправка письма
    send_mail(
        subject=f"Подтверждение покупки пакета {subscription.package.name}",
        message=f"Вы успешно приобрели пакет {subscription.package.name}.",
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user_email],
        html_message=email_html,
        fail_silently=False,
    )

def create_package_payment(request, package_id):
    """
    Создание платежа в ЮКассе для покупки пакета.
    """
    import traceback

    if request.method != "POST":
        return JsonResponse({"error": "Метод не поддерживается"}, status=405)

    try:
        package = get_object_or_404(EventPackage, id=package_id)
        user = request.user

        # Проверка, что пользователь авторизован
        if not user.is_authenticated:
            return JsonResponse({"error": "Пользователь не авторизован"}, status=403)

        # Проверка, что пакет доступен для покупки
        if not package:
            return JsonResponse({"error": "Пакет не найден"}, status=404)

        # Проверяем, есть ли у пользователя активная подписка
        active_subscription = UserPackageSubscription.objects.filter(
            user=user, is_active=True
        ).first()

        if active_subscription:
            # Если есть активная подписка, предлагаем выбор: изменить сейчас или запланировать
            return JsonResponse({
                "has_active_subscription": True,
                "current_package": {
                    "id": active_subscription.package.id,
                    "name": active_subscription.package.name,
                    "end_date": active_subscription.end_date.strftime('%Y-%m-%d %H:%M:%S')
                },
                "new_package": {
                    "id": package.id,
                    "name": package.name,
                    "price": str(package.price)
                }
            })

        # Определяем цену пакета (в реальном проекте цена должна быть в модели пакета)
        package_price = package.price  # Используем реальную цену пакета

        # Создание платежа в ЮКассе
        payment = Payment.create(
            {
                "amount": {"value": str(package_price), "currency": "RUB"},
                "confirmation": {
                    "type": "redirect",
                    "return_url": request.build_absolute_uri(
                        f"/payment/package_success/{package_id}/"
                    ),
                },
                "capture": True,
                "description": f"Оплата пакета {package.name} для пользователя {user.email}",
                "metadata": {"package_id": package_id, "user_id": user.id},
            },
            uuid.uuid4(),
        )

        return JsonResponse(
            {
                "payment_url": payment.confirmation.confirmation_url,
                "package_id": package_id,
            }
        )

    except Exception as e:
        traceback.print_exc()
        return JsonResponse({"error": str(e)}, status=500)

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

        if change_type == "immediate":
            # Немедленная смена пакета - отменяем текущую подписку
            active_subscription.is_active = False
            active_subscription.save()

            # Создаем новую подписку с выбранным пакетом
            new_subscription = UserPackageSubscription.objects.create(
                user=user,
                package=package,
                subscription_type='monthly' if package.is_monthly else 'one_time',
                is_active=True
            )

            # Создаем платеж в ЮКассе для новой подписки
            payment = Payment.create(
                {
                    "amount": {"value": str(package.price), "currency": "RUB"},
                    "confirmation": {
                        "type": "redirect",
                        "return_url": request.build_absolute_uri(
                            f"/payment/package_success/{package_id}/"
                        ),
                    },
                    "capture": True,
                    "description": f"Оплата пакета {package.name} для пользователя {user.email}",
                    "metadata": {"package_id": package_id, "user_id": user.id},
                },
                uuid.uuid4(),
            )

            return JsonResponse({
                "status": "success",
                "message": "Пакет успешно изменен",
                "new_subscription": {
                    "id": new_subscription.id,
                    "package_name": new_subscription.package.name,
                    "end_date": new_subscription.end_date.strftime('%Y-%m-%d %H:%M:%S')
                },
                "payment_url": payment.confirmation.confirmation_url
            })

        elif change_type == "scheduled":
            # Запланированная смена пакета - планируем изменение на дату окончания текущей подписки
            active_subscription.schedule_package_change(package)

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
        traceback.print_exc()
        return JsonResponse({"error": str(e)}, status=500)

def create_invoice(request, package_id):
    """
    Создание счета для юридических лиц.
    """
    import traceback

    if request.method != "POST":
        return JsonResponse({"error": "Метод не поддерживается"}, status=405)

    try:
        package = get_object_or_404(EventPackage, id=package_id)
        user = request.user
        admin_email = request.POST.get("admin_email")

        # Проверка, что пользователь авторизован
        if not user.is_authenticated:
            return JsonResponse({"error": "Пользователь не авторизован"}, status=403)

        # Проверка, что пакет доступен для покупки
        if not package:
            return JsonResponse({"error": "Пакет не найден"}, status=404)

        # Проверка, что указан email администратора
        if not admin_email:
            return JsonResponse({"error": "Не указан email администратора"}, status=400)

        # Здесь должна быть логика создания счета для юридического лица
        # Например, сохранение заявки в базу данных или отправка уведомления администратору

        # Отправка уведомления администратору
        from django.core.mail import send_mail
        from django.conf import settings

        subject = f"Заявка на выставление счета для пакета {package.name}"
        message = f"""
        Пользователь {user.email} запросил выставление счета для покупки пакета {package.name}.

        Детали:
        - Пакет: {package.name}
        - Цена: {package.price} RUB
        - Пользователь: {user.email} ({user.first_name} {user.last_name})
        - Email для связи: {admin_email}

        Пожалуйста, свяжитесь с пользователем и выставите счет вручную.
        """

        # Отправка письма администратору
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[admin_email, settings.DEFAULT_FROM_EMAIL],  # Отправляем и администратору, и на основной email
            fail_silently=False,
        )

        return JsonResponse(
            {
                "status": "success",
                "message": "Заявка на выставление счета успешно отправлена администратору",
                "package_id": package_id,
            }
        )

    except Exception as e:
        traceback.print_exc()
        return JsonResponse({"error": str(e)}, status=500)


def bulk_buy_tickets(request, event_id):
    """
    API для покупки нескольких типов билетов за один раз.
    """
    import traceback

    if request.method != 'POST':
        logger.error('[bulk_buy] Метод не POST', extra={'event_id': event_id})
        return JsonResponse({'error': 'Метод не поддерживается'}, status=405)
    
    try:
        # Парсим JSON тело запроса
        data = json.loads(request.body)
        logger.info('[bulk_buy] Получен запрос на покупку', extra={
            'event_id': event_id,
            'tickets': data.get('tickets'),
            'email': data.get('email')
        })
        
        event = get_object_or_404(Event, id=event_id)
        logger.info('[bulk_buy] Мероприятие найдено', extra={'event_title': event.title})
        
        # Получаем данные
        tickets_data = data.get('tickets', [])
        total_price = float(data.get('total_price', 0))
        buyer_name = data.get('name', '').strip()
        email = data.get('email', '').strip()
        phone = data.get('phone', '').strip()
        
        logger.info('[bulk_buy] Данные получены', extra={
            'tickets_count': len(tickets_data),
            'total_price': total_price,
            'buyer_name': buyer_name,
            'email': email
        })
        
        # === ПРОВЕРКА ЛИМИТА БЕЗ СОЗДАНИЯ ЗАКАЗА ===
        if data.get('check_free_limit'):
            email = data.get('email', '').strip()
            if not email:
                return JsonResponse({'error': 'Укажите email'}, status=400)
            
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
        
        # Валидация
        if not tickets_data:
            logger.error('[bulk_buy] Корзина пуста', extra={'event_id': event_id})
            return JsonResponse({'error': 'Выберите хотя бы один билет'}, status=400)
        
        if not email:
            logger.error('[bulk_buy] Email не указан', extra={'event_id': event_id})
            return JsonResponse({'error': 'Укажите email'}, status=400)
        
        # Подсчитываем запрашиваемое количество бесплатных билетов
        requested_free_quantity = 0
        for ticket_item in tickets_data:
            ticket_id = ticket_item.get('id')
            quantity = int(ticket_item.get('quantity', 0))
            if quantity > 0:
                ticket = Ticket.objects.filter(id=ticket_id).first()
                if ticket and float(ticket.price) == 0:
                    requested_free_quantity += quantity
        
        # Проверяем лимит: не более 2 бесплатных билетов на мероприятие для пользователя
        if requested_free_quantity > 0:
            # Считаем сколько бесплатных билетов пользователь уже получил НА ЭТОМ мероприятии
            event_free_count = Order.objects.filter(
                participant_data__email=email,
                ticket__event=event,
                ticket__price=0,
                payment_status='succeeded'
            ).aggregate(total=Sum('quantity'))['total'] or 0
            event_free_count = int(event_free_count)
            
            logger.info('[bulk_buy] Проверка лимита бесплатных билетов', extra={
                'email': email,
                'event_id': event_id,
                'already_free_this_event': event_free_count,
                'requested': requested_free_quantity,
                'total': event_free_count + requested_free_quantity
            })
            
            if event_free_count + requested_free_quantity > 2:
                remaining = 2 - event_free_count
                if remaining > 0:
                    logger.warning('[bulk_buy] Лимит бесплатных билетов (остаток)', extra={
                        'email': email,
                        'event_id': event_id,
                        'already_free': event_free_count,
                        'requested': requested_free_quantity,
                        'remaining': remaining
                    })
                    return JsonResponse({
                        'error': f'На это мероприятие можно получить не более 2 бесплатных билетов. У вас уже есть {event_free_count}, можно ещё {remaining}.'
                    }, status=400)
                else:
                    logger.warning('[bulk_buy] Лимит бесплатных билетов (исчерпан)', extra={
                        'email': email,
                        'event_id': event_id,
                        'already_free': event_free_count,
                        'requested': requested_free_quantity
                    })
                    return JsonResponse({
                        'error': 'Вы уже получили максимальное количество бесплатных билетов на это мероприятие (2).'
                    }, status=400)
        
        # Создаём participant_data
        participant_data = {
            'name': buyer_name,
            'email': email,
            'phone': phone
        }

        # Создаём заказы для каждого типа билета
        orders = []
        with transaction.atomic():
            logger.info('[bulk_buy] Начало транзакции создания заказов', extra={'event_id': event_id})
            
            for ticket_item in tickets_data:
                ticket_id = ticket_item.get('id')
                quantity = int(ticket_item.get('quantity', 0))
                
                if quantity <= 0:
                    logger.warning('[bulk_buy] Пропуск билета с quantity=0', extra={'ticket_id': ticket_id})
                    continue
                
                ticket = get_object_or_404(Ticket, id=ticket_id, event=event)
                logger.info('[bulk_buy] Проверка доступности билета', extra={
                    'ticket_id': ticket_id,
                    'ticket_name': ticket.name,
                    'quantity': quantity
                })
                
                # Проверяем доступность
                if not ticket.is_available(quantity):
                    available = ticket.get_available_count()
                    logger.error('[bulk_buy] Билет недоступен', extra={
                        'ticket_id': ticket_id,
                        'requested': quantity,
                        'available': available
                    })
                    return JsonResponse({
                        'error': f'Билет "{ticket.name}" недоступен в количестве {quantity}. Доступно: {available}'
                    }, status=400)
                
                # Создаём заказ
                order = Order.objects.create(
                    ticket=ticket,
                    participant_data=participant_data,
                    total_price=ticket.price * quantity,
                    quantity=quantity,
                    payment_status='pending',
                    purchase_type='paid_ticket',
                    payment_deadline=timezone.now() + timedelta(minutes=10),
                )

                orders.append(order)
                logger.info('[bulk_buy] Заказ создан', extra={
                    'order_id': order.id,
                    'ticket_name': ticket.name,
                    'quantity': quantity,
                    'total_price': str(order.total_price)
                })
            
            logger.info('[bulk_buy] Все заказы созданы', extra={
                'orders_count': len(orders),
                'event_id': event_id
            })
        
        # Определяем логику оплаты
        # Сначала обрабатываем бесплатные билеты отдельно
        free_orders = [o for o in orders if o.total_price == 0]
        paid_orders = [o for o in orders if o.total_price > 0]
        
        if free_orders:
            logger.info('[bulk_buy] Обработка бесплатных билетов', extra={'orders_count': len(free_orders)})
            
            for order in free_orders:
                order.payment_status = 'succeeded'
                order.is_paid = True
                order.purchase_type = 'free_registration'
                order.save()
                logger.info('[bulk_buy] Бесплатный заказ оплачен', extra={'order_id': order.id})

            # Отправка писем для бесплатных билетов
            for order in free_orders:
                try:
                    send_order_confirmation_email(order, request)
                    logger.info('[bulk_buy] Письмо отправлено', extra={'order_id': order.id, 'email': email})
                except Exception as e:
                    logger.error('[bulk_buy] Ошибка отправки письма', extra={'order_id': order.id, 'email': email, 'error': str(e)}, exc_info=True)

            logger.info('[bulk_buy] Бесплатные билеты успешно оформлены', extra={
                'orders_count': len(free_orders)
            })
            
            # Считаем общее количество бесплатных билетов пользователя
            total_free = Order.objects.filter(
                participant_data__email=email,
                ticket__price=0,
                payment_status='succeeded'
            ).aggregate(total=Sum('quantity'))['total'] or 0
            
        # Убираем бесплатные заказы из списка для платной обработки
        orders = paid_orders
        
        if not orders:
            # Все билеты бесплатные
            return JsonResponse({
                'success': True,
                'message': 'Билеты успешно оформлены! Проверьте вашу почту.',
                'orders': [o.id for o in free_orders],
                'free_tickets_count': total_free
            })
        
        # Платные билеты - создаём платёж
        logger.info('[bulk_buy] Создание платежа ЮКасса', extra={'orders_count': len(orders)})
        
        # Объединяем все заказы в один платёж
        combined_total = sum(o.total_price for o in orders)
        
        payment = Payment.create(
            {
                "amount": {"value": str(combined_total), "currency": "RUB"},
                "confirmation": {
                    "type": "redirect",
                    "return_url": request.build_absolute_uri(
                        f"/payment/success/{orders[0].id}/"
                    ),
                },
                "capture": True,
                "description": f"Оплата заказа для мероприятия {event.title}",
                "metadata": {
                    "order_ids": json.dumps([o.id for o in orders]),
                    "event_id": event_id,
                    "free_order_ids": json.dumps([o.id for o in free_orders]) if free_orders else None
                },
            },
            uuid.uuid4(),
        )

        # Сохраняем ID платежей для каждого заказа
        for order in orders:
            order.payment_status = 'pending'
            order.yookassa_payment_id = payment.id
            order.save()
            logger.info('[bulk_buy] Сохранён ID платежа для заказа', extra={
                'order_id': order.id,
                'yookassa_id': payment.id
            })
        
        logger.info('[bulk_buy] Платёж создан успешно', extra={
            'payment_id': payment.id,
            'orders_count': len(orders)
        })
        
        return JsonResponse({
            'success': True,
            'payment_url': payment.confirmation.confirmation_url,
            'order_ids': [o.id for o in orders],
            'order_id': orders[0].id if orders else None,
            'free_tickets_count': total_free if free_orders else 0
        })
        
    except json.JSONDecodeError:
        logger.error('[bulk_buy] Неверный JSON в запросе', extra={'event_id': event_id})
        return JsonResponse({'error': 'Неверный формат данных'}, status=400)
    
    except Exception as e:
        traceback.print_exc()
        logger.error('[bulk_buy] Критическая ошибка', extra={
            'event_id': event_id,
            'error': str(e)
        }, exc_info=True)
        return JsonResponse({'error': str(e)}, status=500)


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

        # Данные участника из формы
        participant_data = {
            "name": request.POST.get("name"),
            "email": request.POST.get("email"),
            "phone": request.POST.get("phone"),
        }

        # Проверка, выбран ли чекбокс "Заявка организатору"
        request_to_organizer = request.POST.get("request_to_organizer") == "on"
        if request_to_organizer:
            # Обработка заявки организатору
            from core.models import SupportTicket, SupportMessage, User

            # Проверка обязательных полей
            if not all(participant_data.values()):
                from django.shortcuts import render
                return render(
                    request,
                    "buy_ticket.html",
                    {
                        "ticket": ticket,
                        "error_message": "Все поля обязательны для заполнения."
                    },
                )

            # Создаём или получаем пользователя
            user, created = User.objects.get_or_create(
                username=participant_data["email"],
                defaults={
                    "email": participant_data["email"],
                    "first_name": participant_data["name"].split()[0] if participant_data["name"] else "",
                    "last_name": " ".join(participant_data["name"].split()[1:]) if len(participant_data["name"].split()) > 1 else "",
                }
            )

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

        quantity = int(request.POST.get("quantity", 1))
        if not ticket.is_available() or ticket.get_available_count() < quantity:
            from django.shortcuts import render
            return render(
                request,
                "buy_ticket.html",
                {
                    "ticket": ticket,
                    "error_message": f"Запрошенное количество билетов {ticket.name} недоступно"
                },
            )

        # Проверка максимального количества билетов за один заказ для бесплатных билетов
        if ticket.price == 0:
            max_tickets_per_order = 2  # Максимальное количество бесплатных билетов за один заказ
            if quantity > max_tickets_per_order:
                from django.shortcuts import render
                return render(
                    request,
                    "buy_ticket.html",
                    {
                        "ticket": ticket,
                        "error_message": f"За один заказ можно получить не более {max_tickets_per_order} бесплатных билетов."
                    },
                )

        # Проверка доступности билетов
        if not ticket.is_available() or ticket.get_available_count() < quantity:
            return JsonResponse(
                {"error": f"Запрошенное количество билетов {ticket.name} недоступно"},
                status=400,
            )

        # Проверка на бесплатные билеты
        if ticket.price == 0:
            # Проверка количества бесплатных билетов на одно устройство
            device_id = request.session.session_key
            free_tickets_count = Order.objects.filter(
                participant_data__email=participant_data["email"],
                ticket__price=0,
                payment_status="succeeded"
            ).count()

            if free_tickets_count >= 2:
                from django.shortcuts import render
                return render(
                    request,
                    "buy_ticket.html",
                    {
                        "ticket": ticket,
                        "error_message": "На одно устройство можно получить не более 2 бесплатных билетов."
                    },
                )

            # Создание заказа для бесплатного билета
            order = Order.objects.create(
                ticket=ticket,
                participant_data=participant_data,
                total_price=0,
                quantity=quantity,
                payment_status="succeeded",
                is_paid=True,
                purchase_type="free_registration",
            )

            # Отправка билетов на почту
            send_order_confirmation_email(order, request)

            return redirect(f"/payment/success/{order.id}/")

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
            payment_deadline=timezone.now() + timedelta(
                hours=24 if reserve_without_payment else 10
            ),
        )

        if reserve_without_payment:
            # Отправка письма с кнопкой для оплаты
            send_reservation_email(order, request)
            return redirect(f"/payment/success/{order.id}/")
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
                {
                    "payment_url": payment.confirmation.confirmation_url,
                    "order_id": order.id,
                }
            )

    except Exception as e:
        traceback.print_exc()
        return JsonResponse({"error": str(e)}, status=500)


@csrf_exempt
def yookassa_webhook(request):
    """Обработка уведомлений от ЮКассы (вебхуки)."""
    try:
        # Получение и проверка данных из вебхука
        event_json = json.loads(request.body)
        if event_json["event"] == "payment.succeeded":
            payment = event_json["object"]
            metadata = payment.get("metadata", {})

            # Проверяем, является ли платеж за пакет
            if "package_id" in metadata and "user_id" in metadata:
                package_id = metadata["package_id"]
                user_id = metadata["user_id"]

                # Используем filter() вместо get()
                subscriptions = UserPackageSubscription.objects.filter(
                    user_id=user_id,
                    package_id=package_id,
                    is_active=True
                )

                if subscriptions.exists():
                    # Если подписка уже существует, обновляем её
                    subscription = subscriptions.first()
                    subscription.end_date = timezone.now() + timezone.timedelta(days=30 if subscription.package.is_monthly else 365)
                    subscription.save()
                else:
                    # Если подписки нет, создаем новую
                    package = EventPackage.objects.get(id=package_id)
                    user = CustomUser.objects.get(id=user_id)

                    # Определяем дату окончания подписки
                    if package.is_monthly:
                        end_date = timezone.now() + timezone.timedelta(days=30)
                        subscription_type = "monthly"
                    else:
                        end_date = timezone.now() + timezone.timedelta(days=365)
                        subscription_type = "one_time"

                    # Создаем новую подписку
                    subscription = UserPackageSubscription.objects.create(
                        user=user,
                        package=package,
                        end_date=end_date,
                        subscription_type=subscription_type,
                        is_active=True
                    )

                # Отправка уведомления на почту
                send_package_purchase_email(subscription, request)

            else:
                # Обработка платежа за билет
                logger.info('[webhook] payment.succeeded: поиск заказа', extra={'payment_id': payment["id"]})
                orders = []
                try:
                    order = Order.objects.get(yookassa_payment_id=payment["id"])
                    orders = [order]
                    logger.info('[webhook] Найден одиночный заказ', extra={'order_id': order.id})
                except Order.DoesNotExist:
                    logger.warning('[webhook] Одиночный заказ не найден, проверяем bulk-buy', extra={'payment_id': payment["id"]})
                    metadata = payment.get("metadata", {})
                    order_ids_raw = metadata.get("order_ids", [])
                    order_ids = []
                    if isinstance(order_ids_raw, str):
                        try:
                            order_ids = json.loads(order_ids_raw)
                        except json.JSONDecodeError:
                            order_ids = []
                    elif isinstance(order_ids_raw, list):
                        order_ids = order_ids_raw

                    if order_ids:
                        # Сначала пытаемся найти по payment_id
                        orders = Order.objects.filter(yookassa_payment_id=payment["id"], id__in=order_ids)
                        if not orders.exists():
                            logger.warning('[webhook] Не найдено по payment_id, ищу только по ID', extra={'order_ids': order_ids})
                            orders = Order.objects.filter(id__in=order_ids)
                        
                        if orders.exists():
                            for o in orders:
                                o.yookassa_payment_id = payment["id"]
                                o.save()
                        else:
                            logger.error('[webhook] Заказы не найдены в БД', extra={'order_ids': order_ids})
                            raise Http404("Order with the specified Yookassa payment ID does not exist")
                    else:
                        logger.error('[webhook] order_ids пуст или отсутствует в метаданных')
                        raise Http404("Order with the specified Yookassa payment ID does not exist")

                if orders:
                    for order in orders:
                        try:
                            order.payment_status = "succeeded"
                            order.is_paid = True
                            order.yookassa_payment_data = payment
                            
                            order.save()
                            
                            logger.info('[webhook] Заказ обновлен', extra={'order_id': order.id, 'status': 'succeeded'})
                            
                            
                            try:
                                send_order_confirmation_email(order, request)
                                logger.info('[webhook] Письмо отправлено', extra={'order_id': order.id, 'email': order.participant_data.get('email')})
                            except Exception as e:
                                logger.error('[webhook] Ошибка отправки письма', extra={'order_id': order.id, 'error': str(e)}, exc_info=True)
                        except Exception as e:
                            logger.error('[webhook] Ошибка обновления заказа', extra={'order_id': order.id, 'error': str(e)}, exc_info=True)
                else:
                    logger.error('[webhook] orders не определен после поиска')

        elif event_json["event"] == "payment.canceled":
            payment = event_json["object"]
            order_id = payment.get("id")
            if not order_id:
                raise Http404("Invalid Yookassa payment data")
            order = Order.objects.get(yookassa_payment_id=order_id)
            order.payment_status = "canceled"
            order.save()

        elif event_json["event"] == "refund.succeeded":
            payment = event_json["object"]
            order_id = payment.get("payment_id")
            if not order_id:
                raise Http404("Invalid Yookassa refund data")
            order = Order.objects.get(yookassa_payment_id=order_id)
            order.payment_status = "refunded"
            order.save()

        return HttpResponse(status=200)

    except Exception as e:
        print(f"Error in yookassa_webhook: {e}")
        return JsonResponse({"error": str(e)}, status=400)


def refund_ticket(request, order_id):
    """
    Возврат билета через ЮКассу.
    """
    import traceback

    try:
        print("Starting refund process for order_id:", order_id)
        order = get_object_or_404(Order, id=order_id)
        print(
            "Order found:",
            order.id,
            "Status:",
            order.payment_status,
            "YooKassa Payment ID:",
            order.yookassa_payment_id,
        )

        if order.payment_status != "succeeded" or not order.is_paid:
            return render(
                request,
                "refund_error.html",
                {"error": "Заказ не оплачен или билет не был оплачен"},
            )

        # Проверка срока возврата
        if order.ticket.event.get_refund_deadline() < timezone.now():
            return render(
                request, "refund_error.html", {"error": "Срок возврата истек"}
            )

        print("Attempting to refund payment with ID:", order.yookassa_payment_id)
        from yookassa import Refund

        # Создание возврата в ЮКассе
        refund = Refund.create(
            {
                "payment_id": order.yookassa_payment_id,
                "amount": {"value": str(order.total_price), "currency": "RUB"},
            },
            uuid.uuid4(),
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
    Обновляет ВСЕ заказы, привязанные к тому же платежу ЮКассы.
    """
    from yookassa import Payment

    order = get_object_or_404(Order, id=order_id)

    # Если есть yookassa_payment_id — ищем все заказы с этим ID
    if order.yookassa_payment_id:
        try:
            yookassa_payment = Payment.find_one(order.yookassa_payment_id)
            if yookassa_payment and yookassa_payment.status == "succeeded":
                # Обновляем ВСЕ заказы с этим платежным ID
                orders_to_update = Order.objects.filter(
                    yookassa_payment_id=order.yookassa_payment_id
                )
                sent_emails = set()

                for o in orders_to_update:
                    if o.payment_status != "succeeded":
                        o.payment_status = "succeeded"
                        o.is_paid = True
                        o.save()
                        logger.info('[success] Заказ обновлён', extra={
                            'order_id': o.id,
                            'payment_id': order.yookassa_payment_id
                        })

                    # Отправляем письмо только один раз
                    if o.id not in sent_emails:
                        try:
                            send_order_confirmation_email(o, request)
                            sent_emails.add(o.id)
                        except Exception as e:
                            logger.error('[success] Ошибка отправки письма', extra={
                                'order_id': o.id,
                                'error': str(e)
                            }, exc_info=True)
        except Exception as e:
            logger.error('[success] Ошибка проверки статуса ЮКассы', extra={
                'order_id': order.id,
                'error': str(e)
            }, exc_info=True)

    return render(request, "payment_success.html", {"order": order})

def pay_reserved_order(request, order_id):
    """
    Оплата забронированного билета.
    """
    import traceback
    from yookassa import Payment

    try:
        order = get_object_or_404(Order, id=order_id)

        if order.payment_status not in ["reserved", "pending"]:
            return render(
                request,
                "refund_error.html",
                {"error": "Этот заказ не может быть оплачен"},
            )

        if order.payment_status == "pending" and order.yookassa_payment_id:
            # Если платеж уже создан, перенаправляем на существующую ссылку для оплаты
            try:
                from yookassa import Payment

                payment = Payment.find_one(order.yookassa_payment_id)
                if payment and payment.status == "pending":
                    return redirect(payment.confirmation.confirmation_url)
            except Exception as e:
                traceback.print_exc()

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

def package_success(request, package_id):
    """
    Страница успешной оплаты пакета.
    """
    package = get_object_or_404(EventPackage, id=package_id)
    return render(request, "payment/package_success.html", {"package": package})
