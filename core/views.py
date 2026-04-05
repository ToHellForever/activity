from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth import logout as auth_logout
from .forms import CustomAuthenticationForm, CustomUserCreationForm
from django.views.decorators.cache import never_cache
from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate
from .forms import CustomAuthenticationForm
from .models import Event, Ticket
from .forms import EventForm
from django.contrib.auth.decorators import login_required

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


