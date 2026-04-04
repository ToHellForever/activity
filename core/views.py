from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate, logout
from .forms import CustomAuthenticationForm, CustomUserCreationForm

def login_view(request):
    if request.user.is_authenticated:
        # Если пользователь уже вошел, редиректим в нужный кабинет
        if request.user.user_type == 'partner':
            return redirect('partner:dashboard')
        else:
            return redirect('visitor:dashboard')
            
    if request.method == 'POST':
        form = CustomAuthenticationForm(request.POST)
        if form.is_valid():
            user = form.cleaned_data['user']
            login(request, user) # Создаем сессию

            # Редиректим в зависимости от роли
            if user.user_type == 'partner':
                return redirect('partner:dashboard')
            else:
                return redirect('visitor:dashboard')
    else:
        form = CustomAuthenticationForm()
    
    return render(request, 'registration/login.html', {'form': form})


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