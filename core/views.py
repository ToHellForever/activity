from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth import logout as auth_logout
from .forms import CustomAuthenticationForm, CustomUserCreationForm
from django.views.decorators.cache import never_cache
# core/views.py

from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate
from .forms import CustomAuthenticationForm


@never_cache
def login_view(request):
    if request.user.is_authenticated:
        # Если пользователь уже вошел, сразу редиректим его в нужный кабинет
        if request.user.user_type == 'partner':
            return redirect('partner:dashboard')
        else:
            return redirect('visitor:dashboard')

    if request.method == 'POST':
        form = CustomAuthenticationForm(request.POST)
        if form.is_valid():
            user = form.cleaned_data['user']
            login(request, user)
            if user.user_type == 'partner':
                return redirect('partner:dashboard')
            else:
                return redirect('visitor:dashboard')
    else:
        form = CustomAuthenticationForm()
    
    return render(request, 'registration/login.html', {'form': form})

@never_cache
def register_view(request):
    """Обрабатывает регистрацию нового пользователя."""
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save() # Сохраняем пользователя в БД
            # Сразу логиним пользователя после регистрации
            login(request, user)
            
            # Редирект в зависимости от выбранной роли при регистрации
            if user.user_type == 'partner':
                return redirect('partner:dashboard')
            else:
                return redirect('visitor:dashboard')
    else:
        form = CustomUserCreationForm()
    
    return render(request, 'registration/register.html', {'form': form})


def custom_logout(request):
    """
    Кастомная функция для выхода из системы.
    Гарантирует редирект на страницу входа.
    """
    # Выполняем стандартное действие выхода
    auth_logout(request)
    
    # Редиректим на страницу входа по имени URL
    return redirect('login')