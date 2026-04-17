from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from core.models import Order

@login_required
def visitor_dashboard(request):
    # Проверяем тип пользователя
    if request.user.user_type != 'visitor':
        # Если зашел партнер, перенаправляем его на его кабинет
        return redirect('partner:dashboard')
        
    # Получаем заказы текущего пользователя по email
    user_orders = Order.objects.filter(
        participant_data__email=request.user.email
    ).select_related('ticket__event').order_by('-created_at')
    
    # Логика для посетителя
    context = {
        'user': request.user,
        'user_orders': user_orders
    }
    return render(request, 'visitor/dashboard.html', context)