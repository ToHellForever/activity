from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth import logout as auth_logout
from .forms import CustomAuthenticationForm, CustomUserCreationForm
from django.views.decorators.cache import never_cache
from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate
from .forms import CustomAuthenticationForm
from .models import Event, Ticket
from django.contrib.auth.decorators import login_required
from core.forms import SupportTicketForm
from .models import SupportTicket, SupportMessage
from django import forms
# require_POST
from django.views.decorators.http import require_POST

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
def support_dashboard(request):
    """
    Главная страница поддержки. Слева список тикетов, справа чат.
    """
    # --- НОВАЯ ЛОГИКА: Создание тикета на этой же странице ---
    if request.method == 'POST':
        # Проверяем, пришли ли данные для создания НОВОГО тикета
        new_subject = request.POST.get('new_subject')
        new_message = request.POST.get('new_message')
        
        if new_subject and new_message:
            # Создаем новый тикет
            ticket = SupportTicket.objects.create(
                subject=new_subject,
                user=request.user,
                status='new'
            )
            # Создаем первое сообщение в чате
            SupportMessage.objects.create(
                ticket=ticket,
                user=request.user,
                is_from_user=True,
                text=new_message
            )
            # Перенаправляем на эту же страницу, но с выбранным новым тикетом
            return redirect(f'/support/?ticket_id={ticket.id}')
    
    # --- СТАРАЯ ЛОГИКА: Отображение страницы ---
    tickets = SupportTicket.objects.filter(user=request.user).order_by('-created_at')
    selected_ticket = None
    chat_messages = []

    if request.GET.get('ticket_id'):
        ticket_id = request.GET.get('ticket_id')
        selected_ticket = get_object_or_404(SupportTicket, id=ticket_id, user=request.user)
        chat_messages = selected_ticket.messages.all()

    context = {
        'tickets': tickets,
        'selected_ticket': selected_ticket,
        'chat_messages': chat_messages,
    }
    return render(request, 'support_dashboard.html', context)


# --- VIEW для отправки сообщения (через POST) ---
@require_POST
@login_required
def send_support_message(request):
    """
    Обрабатывает отправку сообщения в чат.
    """
    ticket_id = request.POST.get('ticket_id')
    text = request.POST.get('text')
    
    if ticket_id and text:
        ticket = get_object_or_404(SupportTicket, id=ticket_id, user=request.user)
        SupportMessage.objects.create(
            ticket=ticket,
            user=request.user,
            is_from_user=True,
            text=text
        )
        return redirect(f'/support/?ticket_id={ticket_id}')
    
    messages.error(request, "Ошибка отправки сообщения.")
    return redirect('support_dashboard')