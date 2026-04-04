from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required

@login_required
def partner_dashboard(request):
    if request.user.user_type != 'partner':
        return redirect('visitor:dashboard')
        
    # Логика для партнера
    context = {'user': request.user}
    return render(request, 'partner/dashboard.html', context)