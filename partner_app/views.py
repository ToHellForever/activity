from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from core.models import Event, Ticket, Order
from django.db.models import Sum, Count, Avg
from .forms import EventForm

@login_required
def partner_dashboard(request):
    if request.user.user_type != 'partner':
        return redirect('visitor:dashboard')
        
    # Логика для партнера
    context = {'user': request.user}
    return render(request, 'partner/dashboard.html', context)

@login_required
def create_event(request):
    """
    View для создания нового мероприятия.
    """
    if request.method == 'POST':
        form = EventForm(request.POST, request.FILES) # FILES нужно для загрузки изображений
        if form.is_valid():
            # Сохраняем мероприятие, но пока не коммитим в БД
            event = form.save(commit=False)
            # Привязываем организатора (текущего пользователя)
            event.organizer = request.user
            
            # Сохраняем событие, чтобы получить его ID для билетов
            event.save()
            
            # --- Обрабатываем типы билетов ---
            ticket_data = form.cleaned_data['ticket']
            for line in ticket_data.split('\n'):
                if ':' in line:
                    name, price, quantity = [item.strip() for item in line.split(':', 2)]
                    try:
                        Ticket.objects.create(
                            event=event,
                            name=name,
                            price=float(price.replace(',', '.')),
                            quantity=int(quantity)
                        )
                    except (ValueError, TypeError):
                        # Если данные кривые, пропускаем строку или обрабатываем ошибку
                        continue
            
            # Перенаправляем на страницу списка мероприятий или дашборда
            return redirect('partner:dashboard') 
    else:
        form = EventForm()
    
    return render(request, 'events/event_form.html', {'form': form})

@login_required
def event_list(request):
    """
    Отображает список всех мероприятий текущего партнера.
    """
    # Получаем все мероприятия, где организатор - это текущий пользователь
    events = Event.objects.filter(organizer=request.user).order_by('-date_time')
    
    event_data = []
    for event in events:
        # Суммируем количество проданных билетов по всем типам этого мероприятия
        sold = sum(ticket.orders.count() for ticket in event.tickets.all())
        # Суммируем общее количество доступных билетов
        total = sum(ticket.available_quantity for ticket in event.tickets.all())
        
        event_data.append({
            'event': event,
            'sold': sold,
            'total': total,
        })

    context = {
        'events': event_data,
    }
    return render(request, 'partner/event_list.html', context)


@login_required
def reports(request):
    """
    Отчеты и статистика продаж для партнера.
    """
    orders = Order.objects.filter(ticket__event__organizer=request.user)
    
    # Расчет общей статистики
    total_sales = orders.aggregate(total=Sum('total_price'))['total'] or 0
    tickets_sold = orders.aggregate(count=Count('id'))['count'] or 0
    avg_check = orders.aggregate(avg=Avg('total_price'))['avg'] or 0

    sales_graph_data = {
        '2026-04-01': 15000,
        '2026-04-02': 25000,
        '2026-04-03': 35000,
        '2026-04-04': 10000,
    }
    
    context = {
        'total_sales': total_sales,
        'tickets_sold': tickets_sold,
        'avg_check': avg_check,
        'sales_graph_data': sales_graph_data,
    }
    return render(request, 'partner/reports.html', context)

@login_required
def participant_list(request, event_id):
    """
    Список участников для выбранного мероприятия.
    """
    # Получаем мероприятие или выдаем 404, если его нет или оно чужое
    event = get_object_or_404(Event, id=event_id, organizer=request.user)
    
    orders = Order.objects.filter(ticket__event=event).select_related('ticket')

    context = {
        'event': event,
        'orders': orders,
    }
    return render(request, 'partner/participant_list.html', context)