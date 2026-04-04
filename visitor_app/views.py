from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required

@login_required
def visitor_dashboard(request):
    # Проверяем тип пользователя
    if request.user.user_type != 'visitor':
        # Если зашел партнер, перенаправляем его на его кабинет
        return redirect('partner:dashboard')
        
    # Логика для посетителя
    context = {'user': request.user}
    return render(request, 'visitor/dashboard.html', context)