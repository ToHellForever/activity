"""Дашборд и чаты партнёра."""
from datetime import datetime

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Sum

from core.models import (
    Event,
    Order,
    PayoutRequest,
    UserPackageSubscription,
    SupportTicket,
    PartnerDocument,
    EventPackage,
)
from core.forms import PartnerProfileForm
from ..forms import DocumentUploadForm
from ..models import PartnerProfile


@login_required
def partner_dashboard(request):
    if request.user.user_type != "partner":
        return redirect("visitor:dashboard")

    # Получаем отклоненные мероприятия партнёра
    rejected_events = Event.objects.filter(organizer=request.user, status="rejected")

    rejection_messages = []
    for event in rejected_events:
        if event.rejection_reason:
            rejection_messages.append(
                f"Мероприятие '{event.title}' отклонено. Причина: {event.rejection_reason}"
            )

    # Получаем активные мероприятия партнёра
    active_events = Event.objects.filter(
        organizer=request.user, status="active"
    ).count()

    # Получаем продажи за текущий месяц
    current_month = datetime.now().month
    current_year = datetime.now().year

    monthly_sales = (
        Order.objects.filter(
            ticket__event__organizer=request.user,
            created_at__year=current_year,
            created_at__month=current_month,
        ).aggregate(total=Sum("total_price"))["total"]
        or 0
    )

    # Получаем ожидающие выплаты
    pending_payouts = PayoutRequest.objects.filter(
        organizer=request.user, status="pending"
    ).count()

    # Получаем активную подписку пользователя
    user_subscription = (
        UserPackageSubscription.objects.filter(user=request.user, is_active=True)
        .select_related("package")
        .first()
    )

    # Получаем профиль партнёра
    partner_profile, _ = PartnerProfile.objects.get_or_create(user=request.user)

    # Получаем последний отклонённый документ
    last_rejected_document = None
    last_rejection_reason = None
    if request.user.organizer_status == 'rejected':
        try:
            last_rejected_document = PartnerDocument.objects.filter(
                user=request.user,
                is_approved=False
            ).order_by('-uploaded_at').first()
            if last_rejected_document:
                last_rejection_reason = last_rejected_document.rejection_reason
        except Exception:
            pass

    # Обработка формы редактирования профиля
    if request.method == 'POST':
        profile_form = PartnerProfileForm(request.POST, request.FILES, instance=partner_profile)

        # Обработка удаления видео-визитки
        if 'delete_video' in request.POST:
            if partner_profile.video_business_card:
                partner_profile.delete_file_field("video_business_card")
                partner_profile.video_business_card = None
                partner_profile.save(update_fields=['video_business_card'])
            messages.success(request, "Видео-визитка удалена.")
            return redirect("partner:dashboard")

        # Обработка загрузки документов
        if 'upload_documents' in request.POST:
            document_form = DocumentUploadForm(request.POST, request.FILES, user=request.user)
            if document_form.is_valid():
                doc = document_form.save(commit=False)
                doc.user = request.user
                doc.save()
                request.user.organizer_status = 'pending'
                request.user.save(update_fields=['organizer_status'])
                messages.success(request, "Документы успешно загружены!")
                return redirect("partner:dashboard")
        elif 'resubmit' in request.POST:
            request.user.organizer_status = 'pending'
            request.user.organizer_rejection_reason = None
            request.user.save(update_fields=['organizer_status', 'organizer_rejection_reason'])
            messages.success(request, "Документы отправлены на повторное рассмотрение.")
            return redirect("partner:dashboard")
        else:
            document_form = DocumentUploadForm()

        if profile_form.is_valid():
            profile_form.save()
            # Обновляем email пользователя
            new_email = profile_form.cleaned_data.get('email')
            if new_email and new_email != request.user.email:
                request.user.email = new_email
                request.user.save(update_fields=['email'])
            messages.success(request, "Профиль успешно обновлён!")
            return redirect("partner:dashboard")
    else:
        profile_form = PartnerProfileForm(instance=partner_profile)
        document_form = DocumentUploadForm()

    # Сортируем пакеты от «крутого» к «обычному»: priority > extended > basic
    package_order = {"priority": 0, "extended": 1, "basic": 2}
    packages = sorted(
        EventPackage.objects.all(),
        key=lambda p: package_order.get(p.event_card_type, 99),
    )

    context = {
        "user": request.user,
        "active_events_count": active_events,
        "monthly_sales_sum": monthly_sales,
        "pending_payouts_count": pending_payouts,
        "rejection_messages": rejection_messages,
        "packages": packages,
        "user_subscription": user_subscription,
        "has_active_subscription": user_subscription is not None,
        "partner_profile": partner_profile,
        "profile_form": profile_form,
        "document_form": document_form,
        "last_rejected_document": last_rejected_document,
        "last_rejection_reason": last_rejection_reason,
    }
    return render(request, "partner/dashboard.html", context)


@login_required
def partner_chats(request):
    """Показ чатов — вопросов участников по мероприятиям партнёра."""
    if request.user.user_type != "partner":
        return redirect("visitor:dashboard")

    selected_ticket = None
    chat_messages = []

    # Получаем только тикеты с участниками (ticket_type='participant')
    tickets = SupportTicket.objects.filter(
        event__organizer=request.user,
        ticket_type='participant'
    ).order_by("-created_at")

    if request.GET.get("ticket_id"):
        ticket_id = request.GET.get("ticket_id")
        selected_ticket = get_object_or_404(
            SupportTicket,
            id=ticket_id,
            event__organizer=request.user,
            ticket_type='participant'
        )
        chat_messages = selected_ticket.messages.all()

    partner_profile, _ = PartnerProfile.objects.get_or_create(user=request.user)

    context = {
        "tickets": tickets,
        "selected_ticket": selected_ticket,
        "chat_messages": chat_messages,
        "partner_profile": partner_profile,
    }
    return render(request, "partner/chats.html", context)


@login_required
def partner_chats_list(request):
    """Отображение списка чатов с участниками для партнёра."""
    if request.user.user_type != "partner":
        return redirect("visitor:dashboard")

    # Получаем только тикеты с участниками (ticket_type='participant')
    tickets = SupportTicket.objects.filter(
        event__organizer=request.user,
        ticket_type='participant'
    ).order_by("-created_at")

    partner_profile, _ = PartnerProfile.objects.get_or_create(user=request.user)

    context = {
        "tickets": tickets,
        "partner_profile": partner_profile,
    }
    return render(request, "partner/chats_list.html", context)
