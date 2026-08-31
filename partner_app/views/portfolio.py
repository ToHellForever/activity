"""Портфолио партнёра."""
import logging

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse

from ..models import PortfolioItem, PortfolioImage
from ..forms import PortfolioItemForm

logger = logging.getLogger(__name__)


@login_required
def portfolio_list(request):
    """
    Список элементов портфолио текущего партнёра.
    """
    if request.user.user_type != "partner":
        return redirect("visitor:dashboard")

    if request.user.verification_status != "approved":
        messages.error(
            request,
            "Ваш аккаунт на рассмотрении. Доступ к портфолио ограничен до одобрения."
        )
        return redirect("partner:dashboard")

    portfolio_items = PortfolioItem.objects.filter(
        partner=request.user
    ).order_by("-event_date")

    partner_profile = getattr(request.user, "partner_profile", None)
    context = {
        "portfolio_items": portfolio_items,
        "partner_profile": partner_profile,
    }
    return render(request, "partner/portfolio_list.html", context)


@login_required
def portfolio_create(request):
    """
    Создание нового элемента портфолио.
    """
    if request.user.user_type != "partner":
        return redirect("visitor:dashboard")

    if request.user.verification_status != "approved":
        messages.error(
            request,
            "Ваш аккаунт на рассмотрении. Доступ к портфолио ограничен."
        )
        return redirect("partner:dashboard")

    if request.method == "POST":
        form = PortfolioItemForm(request.POST, request.FILES)
        if form.is_valid():
            item = form.save(commit=False, partner=request.user)
            item.save()

            # Сохраняем изображения (до 5 штук)
            images = request.FILES.getlist("images")
            for i, image in enumerate(images[:5]):
                PortfolioImage.objects.create(
                    portfolio=item,
                    image=image,
                    order=i,
                )

            messages.success(request, "Элемент портфолио успешно добавлен!")
            return redirect("partner:portfolio_list")
        else:
            messages.error(request, "Пожалуйста, исправьте ошибки в форме.")
    else:
        form = PortfolioItemForm()

    partner_profile = getattr(request.user, "partner_profile", None)
    return render(
        request,
        "partner/portfolio_form.html",
        {
            "form": form,
            "partner_profile": partner_profile,
            "is_edit": False,
            "portfolio_item": None,
        },
    )


@login_required
def portfolio_edit(request, item_id):
    """
    Редактирование элемента портфолио.
    """
    if request.user.user_type != "partner":
        return redirect("visitor:dashboard")

    if request.user.verification_status != "approved":
        messages.error(
            request,
            "Ваш аккаунт на рассмотрении. Доступ к портфолио ограничен."
        )
        return redirect("partner:dashboard")

    item = get_object_or_404(PortfolioItem, id=item_id, partner=request.user)

    if request.method == "POST":
        form = PortfolioItemForm(request.POST, request.FILES, instance=item)
        if form.is_valid():
            form.save(partner=request.user)

            # Обработка удаления фото
            deleted_image_ids = request.POST.get("deleted_image_ids", "")
            if deleted_image_ids:
                for image_id in deleted_image_ids.split(","):
                    try:
                        image = PortfolioImage.objects.get(id=image_id, portfolio=item)
                        image.delete()
                    except PortfolioImage.DoesNotExist:
                        pass

            # Обработка замены и добавления новых фото
            images = request.FILES.getlist("images")
            if images:
                # Проверяем лимит
                current_count = item.images.count()
                max_allowed = 5 - current_count
                if len(images) > max_allowed:
                    messages.error(
                        request,
                        f"Нельзя добавить {len(images)} фото. Можно добавить только {max_allowed} (лимит 5)."
                    )
                else:
                    # Добавляем новые фото к существующим
                    for i, image in enumerate(images):
                        PortfolioImage.objects.create(
                            portfolio=item,
                            image=image,
                            order=current_count + i,
                        )

            messages.success(request, "Элемент портфолио успешно обновлён!")
            return redirect("partner:portfolio_list")
        else:
            messages.error(request, "Пожалуйста, исправьте ошибки в форме.")
    else:
        form = PortfolioItemForm(instance=item)

    partner_profile = getattr(request.user, "partner_profile", None)
    return render(
        request,
        "partner/portfolio_form.html",
        {
            "form": form,
            "partner_profile": partner_profile,
            "is_edit": True,
            "portfolio_item": item,
        },
    )


@login_required
def portfolio_delete(request, item_id):
    """
    Удаление элемента портфолио.
    """
    if request.user.user_type != "partner":
        return redirect("visitor:dashboard")

    item = get_object_or_404(PortfolioItem, id=item_id, partner=request.user)

    if request.method == "POST":
        # Каскадное удаление: изображения удалятся автоматически через ForeignKey CASCADE
        # Но нужно убедиться, что файлы удалятся из хранилища
        # Метод delete() в PortfolioImage уже удаляет файл
        item.delete()
        messages.success(request, "Элемент портфолио удалён.")
        # Если AJAX — вернуть JSON, иначе — редирект
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse({"status": "ok"})
        return redirect("partner:portfolio_list")

    partner_profile = getattr(request.user, "partner_profile", None)
    return render(
        request,
        "partner/portfolio_confirm_delete.html",
        {
            "portfolio_item": item,
            "partner_profile": partner_profile,
        },
    )


@login_required
def portfolio_image_delete(request, image_id):
    """
    Удаление отдельного фото из портфолио через AJAX.
    """
    if request.method != "POST":
        return JsonResponse(
            {"status": "error", "message": "Method not allowed"}, status=405
        )

    try:
        image = get_object_or_404(
            PortfolioImage, id=image_id, portfolio__partner=request.user
        )
        # Удаляем файл из хранилища и запись из БД
        image.delete()
        return JsonResponse({"status": "success"})
    except PortfolioImage.DoesNotExist:
        return JsonResponse(
            {"status": "error", "message": "Image not found"}, status=404
        )
    except Exception as e:
        logger.error("Ошибка при удалении фото портфолио: %s", e)
        return JsonResponse(
            {"status": "error", "message": str(e)}, status=500
        )
