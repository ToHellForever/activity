"""Профиль партнёра, смена пароля, инлайн-сохранение полей."""
import logging

from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm

from core.models import PartnerDocument
from core.forms import PartnerProfileForm
from ..forms import DocumentUploadForm
from ..models import PartnerProfile
from .decorators import get_rejection_messages

logger = logging.getLogger(__name__)


@login_required
def profile_edit(request):
    """
    View для редактирования профиля партнера.
    Включает обработку видео-визитки.
    """
    # Получаем или создаём профиль партнёра
    profile, created = PartnerProfile.objects.get_or_create(
        user=request.user,
        defaults={
            'registration_type': 'legal',
        }
    )

    if request.method == "POST":
        # Обработка кнопки "Отправить на пересмотр"
        if "resubmit" in request.POST:
            request.user.organizer_status = "pending"
            request.user.organizer_rejection_reason = None
            request.user.save(update_fields=['organizer_status', 'organizer_rejection_reason'])
            messages.info(request, "Документы отправлены на повторное рассмотрение. Ожидайте решения администратора.")
            return redirect("partner:dashboard")

        # Инициализируем форму профиля с instance=profile
        profile_form = PartnerProfileForm(
            request.POST, request.FILES, instance=profile
        )

        # Эта логика удаляет старую видео-визитку с диска, если был загружен новый файл.
        # Она должна выполняться ДО валидации и сохранения формы.

        # Проверяем, был ли загружен НОВЫЙ файл для поля 'video_business_card'
        new_video_file = request.FILES.get("video_business_card")

        # Если новый файл есть, и у пользователя уже было старое видео...
        if new_video_file and profile.video_business_card:
            # ...то удаляем старый файл из хранилища.
            profile.delete_file_field("video_business_card")

        # Проверяем, был ли загружен НОВЫЙ файл для поля 'logo'
        new_logo_file = request.FILES.get("logo")

        # Если новый файл есть, и у пользователя уже было старое лого...
        if new_logo_file and profile.logo:
            # ...то удаляем старый файл с диска/облака.
            profile.logo.delete(save=False)

        # Обработка удаления видео-визитки
        if "delete_video" in request.POST:
            if profile.video_business_card:
                profile.delete_file_field("video_business_card")
                profile.video_business_card = None
                profile.save(update_fields=["video_business_card"])
            messages.success(request, "Видео-визитка удалена.")
            return redirect("partner:dashboard")

        # Обработка основной формы профиля (включая видео-визитку)
        if profile_form.is_valid():
            profile_form.save()  # Сохранение здесь запустит сигнал для обработки нового видео
        else:
            messages.error(request, "Пожалуйста, исправьте ошибки в форме.")

        # Обработка формы смены пароля
        password_form = PasswordChangeForm(user=request.user, data=request.POST)
        if password_form.is_valid():
            password_form.save()
            update_session_auth_hash(request, password_form.user)

        # Обработка формы загрузки документов
        if "upload_documents" in request.POST:
            document_form = DocumentUploadForm(
                request.POST, request.FILES, user=request.user
            )
            if document_form.is_valid():
                # Если был статус rejected, удаляем старый документ
                if request.user.organizer_status == "rejected":
                    old_doc = PartnerDocument.objects.filter(
                        user=request.user,
                        is_approved=False
                    ).first()
                    if old_doc and old_doc.document:
                        # Удаляем физический файл
                        try:
                            old_doc.document.delete(save=False)
                        except Exception as e:
                            logger.error("Ошибка при удалении старого документа: %s", e)
                        # Удаляем запись из БД
                        old_doc.delete()

                document_form.save()
                request.user.organizer_status = "pending"
                request.user.save()
                messages.success(request, "Ваши документы загружены и находятся на рассмотрении.")
            else:
                messages.error(request, "Ошибка при загрузке документов. Пожалуйста, исправьте ошибки ниже.")
        else:
            messages.success(request, "Ваши изменения успешно сохранены!")
        return redirect("partner:dashboard")

    else:
        profile_form = PartnerProfileForm(instance=profile)
        password_form = PasswordChangeForm(user=request.user)
        document_form = DocumentUploadForm(user=request.user)

    # Если форма документов была отправлена с ошибками, передаём её в контекст
    if request.method == "POST" and "upload_documents" in request.POST:
        document_form = DocumentUploadForm(request.POST, request.FILES, user=request.user)

    # Получаем последний отклонённый документ для отображения причины
    last_rejected_doc = PartnerDocument.objects.filter(
        user=request.user,
        is_approved=False,
        rejection_reason__isnull=False
    ).first()

    context = {
        "user_form": profile_form,
        "password_form": password_form,
        "document_form": document_form,
        "rejection_messages": get_rejection_messages(request),
        "last_rejected_document": last_rejected_doc,
        "partner_profile": profile,
    }
    return render(request, "partner/profile_edit.html", context)


@login_required
def change_password(request):
    """Отдельная страница для смены пароля в личном кабинете партнёра."""
    if request.method == "POST":
        password_form = PasswordChangeForm(user=request.user, data=request.POST)
        if password_form.is_valid():
            password_form.save()
            update_session_auth_hash(request, password_form.user)
            # AJAX-запрос из модального окна на дашборде — возвращаем JSON
            if request.headers.get("x-requested-with") == "XMLHttpRequest":
                return JsonResponse({"status": "success"})
            messages.success(request, "Пароль успешно изменён!")
            return redirect("partner:dashboard")
        # Ошибки валидации для AJAX — отдаём их в JSON, чтобы показать в модалке
        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            errors = {
                field: [str(e) for e in error_list]
                for field, error_list in password_form.errors.items()
            }
            return JsonResponse({"status": "error", "errors": errors})
    else:
        password_form = PasswordChangeForm(user=request.user)

    return render(
        request,
        "change_password.html",
        {"form": password_form, "rejection_messages": get_rejection_messages(request)},
    )


@login_required
@require_POST
def save_field(request):
    """
    Сохранение отдельного поля профиля партнёра через AJAX.
    """
    if request.user.user_type != "partner":
        return JsonResponse({"status": "error", "message": "Доступ запрещён"}, status=403)

    # Обработка загрузки видео
    if request.GET.get("action") == "upload_video":
        video_file = request.FILES.get("video_business_card")
        if video_file:
            profile, _ = PartnerProfile.objects.get_or_create(user=request.user)
            if profile.video_business_card:
                profile.delete_file_field("video_business_card")
            profile.video_business_card = video_file
            profile.save()
            return JsonResponse({"status": "success"})
        return JsonResponse({"status": "error", "message": "Файл не найден"}, status=400)

    field_name = request.POST.get("field_name")
    field_value = request.POST.get("field_value")

    if not field_name:
        return JsonResponse({"status": "error", "message": "Не указано поле"}, status=400)

    # Разрешённые поля для редактирования
    allowed_fields = [
        "description",
        "contact_person",
        "phone",
        "email",
        "additional_email",
        "vk_link",
        "max_link",
        "telegram_link",
    ]

    if field_name not in allowed_fields:
        return JsonResponse({"status": "error", "message": "Недопустимое поле"}, status=400)

    try:
        profile, _ = PartnerProfile.objects.get_or_create(user=request.user)
        setattr(profile, field_name, field_value)
        profile.save(update_fields=[field_name])
        return JsonResponse({"status": "success"})
    except Exception as e:
        logger.error("Ошибка сохранения поля %s: %s", field_name, e)
        return JsonResponse({"status": "error", "message": str(e)}, status=500)
