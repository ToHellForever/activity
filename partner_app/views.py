from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from core.models import Event, Ticket

@login_required
def partner_dashboard(request):
    if request.user.user_type != 'partner':
        return redirect('visitor:dashboard')
        
    # Логика для партнера
    context = {'user': request.user}
    return render(request, 'partner/dashboard.html', context)


@login_required
def event_list(request):
    """
    Отображает список всех мероприятий текущего партнера.
    """
    # Получаем все мероприятия, где организатор - это текущий пользователь
    events = Event.objects.filter(organizer=request.user).order_by('-date_time')
    
    # Для каждого мероприятия нам нужно посчитать проданные билеты
    # Чтобы не делать много запросов к БД, подготовим данные
    event_data = []
    for event in events:
        # Суммируем количество проданных билетов по всем типам этого мероприятия
        sold = sum(ticket.orders.count() for ticket in event.tickets.all())
        # Суммируем общее количество доступных билетов
        total = sum(ticket.available_quantity + sold for ticket in event.tickets.all())
        
        event_data.append({
            'event': event,
            'sold': sold,
            'total': total,
        })

    context = {
        'events': event_data,
    }
    return render(request, 'partner/event_list.html', context)