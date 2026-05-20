from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse, JsonResponse, HttpResponseBadRequest
from django.utils import timezone
from core.models import Order, Ticket
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth import update_session_auth_hash
from django.views.decorators.http import require_http_methods
from core.models import (
    Event,
    Ticket,
    Tag,
    SupportTicket,
    SupportMessage,
    SupportAttachment,
    CustomUser,
    Order,
)
from django.db import models, transaction, IntegrityError
import logging
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
import uuid
import random
import string
import requests
import json
import base64
import qrcode
import io
from django.core.mail import send_mail
from django.shortcuts import (
    render,
    redirect,
    get_object_or_404,
    HttpResponseRedirect,
    reverse,
)
from django.utils import timezone
from core.tasks import generate_payment_link
from django.contrib.sites.shortcuts import get_current_site
from core.tasks import generate_payment_link

logger = logging.getLogger(__name__)


@login_required
def visitor_dashboard(request):
    # Проверяем тип пользователя
    if request.user.user_type != "visitor":
        # Если зашел партнер, перенаправляем его на его кабинет
        return redirect("partner:dashboard")

    # Получаем заказы текущего пользователя по email
    user_orders = (
        Order.objects.filter(participant_data__email=request.user.email)
        .select_related("ticket__event")
        .order_by("-created_at")
    )

    # Логика для посетителя
    context = {"user": request.user, "user_orders": user_orders, "now": timezone.now()}
    return render(request, "visitor/dashboard.html", context)


@login_required
def change_password(request):
    """Отдельная страница для смены пароля в личном кабинете посетителя."""
    if request.method == "POST":
        password_form = PasswordChangeForm(user=request.user, data=request.POST)
        if password_form.is_valid():
            password_form.save()
            update_session_auth_hash(request, password_form.user)
            messages.success(request, "Пароль успешно изменён!")
            return redirect("visitor:dashboard")
    else:
        password_form = PasswordChangeForm(user=request.user)

    return render(request, "change_password.html", {"form": password_form})


