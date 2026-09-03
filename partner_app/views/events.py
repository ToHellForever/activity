"""Мероприятия партнёра: создание, редактирование, удаление, медиафайлы."""
import logging
import os
import tempfile
from datetime import datetime

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.core.mail import send_mail
from django.utils import timezone
from django.conf import settings
from moviepy import VideoFileClip

from core.models import (
    Event,
    Ticket,
    Tag,
    MainTag,
    Category,
    Format,
    EventPackage,
    UserPackageSubscription,
    EventImage,
)
from ..forms import EventForm
from .decorators import check_partner_status, get_rejection_messages

logger = logging.getLogger(__name__)

VIDEO_MAX_DURATION = 310  # 5 минут в секундах
VALID_VIDEO_EXTENSIONS = ['.mp4', '.mov', '.avi']
VALID_IMAGE_EXTENSIONS = ['.jpg', '.jpeg', '.png', '.gif', '.webp']


def _event_form_context(request, form, *, is_edit, ticket_data=None, selected_tag_ids=None,
                        primary_event_image=None):
    """
    Общий контекст для рендера partner/event_form.html.
    Устраняет дублирование одного и того же набора ключей в ~12 местах.
    """
    active_subscription = (
        UserPackageSubscription.objects.filter(user=request.user, is_active=True)
        .select_related("package")
        .first()
    )
    context = {
        "form": form,
        "is_edit": is_edit,
        "ticket_data": ticket_data or [],
        "rejection_messages": get_rejection_messages(request),
        "main_tags": MainTag.objects.prefetch_related("subtags").all(),
        "selected_tag_ids": list(selected_tag_ids) if selected_tag_ids else [],
        "categories": Category.objects.all(),
        "formats": Format.objects.all(),
        "user_subscription": active_subscription,
        "has_active_subscription": active_subscription is not None,
        "has_free_tickets": False,  # обновляется через JavaScript
        "packages": EventPackage.objects.all(),
    }
    if primary_event_image is not None:
        context["primary_event_image"] = primary_event_image
    return context


def _ticket_data_from_post(request, with_description=False):
    """Собирает введённые пользователем билеты для повторного рендера формы."""
    keys = ["ticket_name[]", "ticket_price[]", "ticket_quantity[]"]
    if with_description:
        keys.append("ticket_description[]")
    zipped = zip(*(request.POST.getlist(k) for k in keys))
    fields = ("name", "price", "quantity", "description") if with_description \
        else ("name", "price", "quantity")
    return [
        dict(zip(fields, values))
        for values in zipped
        if values[0] and values[1] and values[2]
    ]


def _check_video_duration(video_file):
    """
    Проверяет длительность загруженного видео (не более 5 минут).
    Возвращает текст ошибки или None, если видео в порядке.
    """
    temp_file_path = None
    try:
        temp_file_path = tempfile.mktemp(suffix=os.path.splitext(video_file.name)[1])

        # Сохраняем видео во временный файл
        with open(temp_file_path, 'wb+') as temp_file:
            for chunk in video_file.chunks():
                temp_file.write(chunk)

        with VideoFileClip(temp_file_path) as video:
            if video.duration > VIDEO_MAX_DURATION:
                return (
                    "Длительность видео превышает 5 минут. "
                    "Пожалуйста, загрузите видео не длиннее 5 минут."
                )

        # Восстанавливаем указатель файла после проверки
        video_file.file.seek(0)
        return None
    except Exception as e:
        logger.error("Ошибка при проверке длительности видео: %s", e, exc_info=True)
        return (
            "Произошла ошибка при проверке длительности видео. "
            "Пожалуйста, попробуйте еще раз."
        )
    finally:
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.unlink(temp_file_path)
            except OSError:
                pass


def _validate_event_files(request):
    """
    Валидирует загружаемые файлы мероприятия (видео, PDF, изображения).
    Возвращает текст ошибки или None.
    """
    video_file = request.FILES.get("video_url")
    if video_file:
        if not any(video_file.name.lower().endswith(ext) for ext in VALID_VIDEO_EXTENSIONS):
            return "Неверный формат видео. Разрешены только файлы MP4, MOV, AVI"
        error = _check_video_duration(video_file)
        if error:
            return error

    pdf_file = request.FILES.get("program_file")
    if pdf_file and not pdf_file.name.lower().endswith('.pdf'):
        return "Неверный формат файла. Разрешены только PDF файлы"

    main_image = request.FILES.get("image")
    if main_image and not any(main_image.name.lower().endswith(ext) for ext in VALID_IMAGE_EXTENSIONS):
        return "Неверный формат основного изображения. Разрешены только JPG, PNG, GIF, WEBP"

    additional_images = request.FILES.getlist("images")
    for image in additional_images:
        if not any(image.name.lower().endswith(ext) for ext in VALID_IMAGE_EXTENSIONS):
            return "Неверный формат дополнительного изображения. Разрешены только JPG, PNG, GIF, WEBP"

    return None


def _parse_ticket_rows(request):
    """Разбирает данные о билетах из таблицы формы."""
    ticket_names = request.POST.getlist("ticket_name[]")
    ticket_prices = request.POST.getlist("ticket_price[]")
    ticket_quantities = request.POST.getlist("ticket_quantity[]")
    ticket_min_quantities = request.POST.getlist("ticket_min_quantity[]")
    ticket_descriptions = request.POST.getlist("ticket_description[]")
    ticket_is_per_person = request.POST.getlist("ticket_is_per_person[]")

    has_free_tickets = False
    has_paid_tickets = False
    for price in ticket_prices:
        if price:
            try:
                price_value = (
                    float(price.replace(",", ".")) if "," in price else float(price)
                )
                if price_value == 0:
                    has_free_tickets = True
                else:
                    has_paid_tickets = True
            except (ValueError, TypeError):
                continue

    return {
        "names": ticket_names,
        "prices": ticket_prices,
        "quantities": ticket_quantities,
        "min_quantities": ticket_min_quantities,
        "descriptions": ticket_descriptions,
        "is_per_person": ticket_is_per_person,
        "has_free": has_free_tickets,
        "has_paid": has_paid_tickets,
    }


def _create_tickets(event, rows, with_color=False):
    """Создаёт билеты мероприятия из разобранных строк формы."""
    for i, (name, price, quantity, description) in enumerate(
        zip(rows["names"], rows["prices"], rows["quantities"], rows["descriptions"])
    ):
        if name and price and quantity:
            try:
                min_quantity = (
                    int(rows["min_quantities"][i])
                    if i < len(rows["min_quantities"]) and rows["min_quantities"][i]
                    else 1
                )
                ticket_kwargs = {
                    "name": name,
                    "price": (
                        float(price.replace(",", ".")) if "," in price else float(price)
                    ),
                    "available_quantity": int(quantity),
                    "ticket_description": description,
                    "is_per_person": (
                        i < len(rows["is_per_person"]) and rows["is_per_person"][i] == "on"
                    ),
                    "min_quantity": min_quantity,
                }
                if with_color:
                    ticket_kwargs["color"] = Ticket().get_random_color()
                event.tickets.create(**ticket_kwargs)
            except (ValueError, TypeError):
                continue


@login_required
@check_partner_status('can_create_events')
def create_event(request):
    """
    View для создания нового мероприятия.
    Видео обрабатывается автоматически через сигналы и Celery.
    """

    # Проверяем наличие активного пакета у пользователя
    active_subscription = (
        UserPackageSubscription.objects.filter(
            user=request.user,
            is_active=True,
        )
        .select_related("package")
        .first()
    )

    if request.method == "POST":
        # Если это редактирование существующего мероприятия
        if 'event_id' in request.POST:
            event = Event.objects.filter(id=request.POST['event_id'], organizer=request.user).first()
            # Те же блокировки, что и в edit_event: модерация и проданные билеты
            if event and event.status == "on_moderation":
                messages.error(
                    request,
                    "Мероприятие находится на модерации. Редактирование станет доступно "
                    "после того, как администратор одобрит или отклонит его.",
                )
                return redirect("partner:partner_event_list")
            if event and event.has_sold_tickets:
                messages.warning(
                    request,
                    "На мероприятие уже проданы билеты — прямое редактирование закрыто. "
                    "Отправьте заявку на изменение.",
                )
                return redirect("partner:request_event_change", event_id=event.id)
            if event and event.package:
                # Если у события уже есть пакет, используем его
                package = event.package
            else:
                # Если нет активного пакета - перенаправляем на покупку
                if not active_subscription:
                    messages.error(
                        request,
                        "Для создания мероприятий необходимо приобрести пакет. Пожалуйста, выберите и оплатите подходящий пакет."
                    )
                    return redirect("partner:dashboard")
                package = active_subscription.package
        else:
            # Если это создание нового мероприятия
            if not active_subscription:
                messages.error(
                    request,
                    "Для создания мероприятий необходимо приобрести пакет. Пожалуйста, выберите и оплатите подходящий пакет."
                )
                return redirect("partner:dashboard")
            package = active_subscription.package

        form = EventForm(request.POST, request.FILES, user=request.user, current_package=package, request=request)

        # Если это редактирование существующего мероприятия — проверяем event.image
        if 'event_id' in request.POST:
            if event and event.image:
                try:
                    if not event.image.storage.exists(event.image.name):
                        event.image.delete(save=False)
                        event.image = None
                        event.save(update_fields=["image"])
                except Exception:
                    pass

        if form.is_valid():
            # Проверяем типы загружаемых файлов
            error = _validate_event_files(request)
            if error:
                messages.error(request, error)
                return render(
                    request,
                    "partner/event_form.html",
                    _event_form_context(request, form, is_edit=False),
                )

            # Проверяем не превышаем ли лимит пакета по количеству фото
            main_image = request.FILES.get("image")
            additional_images = request.FILES.getlist("images")
            total_images = (1 if main_image else 0) + len(additional_images)
            if total_images > package.max_photos:
                additional_photos_allowed = package.max_photos - 1
                messages.error(
                    request,
                    f"Ваш пакет позволяет загрузить не более {package.max_photos} фотографий "
                    f"(1 основное + {additional_photos_allowed} дополнительных). "
                    f"Вы пытаетесь загрузить {total_images} фото."
                )
                return render(
                    request,
                    "partner/event_form.html",
                    _event_form_context(request, form, is_edit=False),
                )

            event = form.save(commit=False)
            event.organizer = request.user
            event.status = "on_moderation"

            # Очищаем медиафайлы, если были отмечены соответствующие флаги
            for field_name in ["video_url", "program_file"]:
                clear_field_name = f"{field_name}-clear"
                if clear_field_name in request.POST:
                    current_file = getattr(event, field_name)
                    if current_file:
                        current_file.delete(save=False)  # Не сохраняем модель здесь
                    setattr(event, field_name, None)

            # Основное фото (отдельный input image), если он есть в запросе
            if main_image:
                event.image = main_image

            event.save()

            # Дополнительные фото (много, input images)
            images = request.FILES.getlist("images")
            if images:
                created_images = []
                for image in images:
                    img = EventImage.objects.create(event=event, image=image)
                    created_images.append(img)

                # Устанавливаем основное фото среди загруженных
                primary_new_index = request.POST.get("primary_new_photo_file_index", "")
                if primary_new_index:
                    try:
                        idx = int(primary_new_index)
                        if 0 <= idx < len(created_images):
                            created_images[idx].is_primary = True
                            created_images[idx].save(update_fields=["is_primary"])
                    except (ValueError, IndexError):
                        pass
                elif created_images:
                    # Если основное не выбрано — первое фото становится основным
                    created_images[0].is_primary = True
                    created_images[0].save(update_fields=["is_primary"])

                # Синхронизируем Event.image с primary EventImage
                event.set_primary_from_event_images()

        else:
            # если форма не валидна — не создаём/сохраняем event здесь
            event = None

        if event is None:
            # просто отдадим форму как есть
            form = EventForm(request.POST, request.FILES, user=request.user, current_package=package, request=request)
            return render(
                request,
                "partner/event_form.html",
                _event_form_context(
                    request,
                    form,
                    is_edit=False,
                    ticket_data=_ticket_data_from_post(request),
                    primary_event_image=None,
                ),
            )

        # Обрабатываем теги из массива ID
        tags_ids = request.POST.getlist("tags")
        if tags_ids:
            # Ограничиваем количество тегов до 5
            selected_tags = tags_ids[:5]
            event.tags.set(selected_tags)

        # Обрабатываем данные о билетах из таблицы
        rows = _parse_ticket_rows(request)

        # Если есть и бесплатные, и платные билеты одновременно
        if rows["has_free"] and rows["has_paid"]:
            messages.error(
                request,
                "Невозможно создать мероприятие с бесплатными и платными билетами одновременно.",
            )
            return render(
                request,
                "partner/event_form.html",
                {
                    "form": form,
                    "is_edit": False,
                    "ticket_data": _ticket_data_from_post(request),
                    "rejection_messages": get_rejection_messages(request),
                    "all_tags": Tag.objects.all(),
                },
            )

        # Создаём билеты (раньше этот цикл был мёртвым кодом после return)
        _create_tickets(event, rows, with_color=True)

        # РЕДИРЕКТИМ пользователя.
        # Обработка видео начнется автоматически через сигнал post_save.
        messages.success(
            request,
            "Мероприятие успешно создано! Видео будет обработано в фоновом режиме.",
        )
        return redirect("partner:partner_event_list")
    else:
        # При загрузке страницы (GET) выводим пакет, который сейчас активен по подписке пользователя
        if not active_subscription:
            messages.warning(
                request,
                "У вас нет активного пакета. Пожалуйста, выберите и купите пакет для создания мероприятий."
            )
            return redirect("partner:dashboard")

        form = EventForm(user=request.user, current_package=active_subscription.package, request=request)

    return render(
        request,
        "partner/event_form.html",
        _event_form_context(request, form, is_edit=False),
    )


def notify_organizer(event):
    subject = f"Ваше мероприятие '{event.title}' одобрено!"
    message = f"Привет, {event.organizer.first_name}!\n\nВаше мероприятие '{event.title}' успешно добавлено на сайт."
    send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [event.organizer.email])


@login_required
@check_partner_status('can_create_events')
def edit_event(request, event_id):
    """
    View для редактирования мероприятия.
    Видео обрабатывается автоматически при замене файла.
    """
    # Получаем активную подписку пользователя
    active_subscription = (
        UserPackageSubscription.objects.filter(
            user=request.user,
            is_active=True,
        )
        .select_related("package")
        .first()
    )

    event = get_object_or_404(Event, id=event_id, organizer=request.user)

    # Мероприятие на модерации — редактирование закрыто до решения администратора
    if event.status == "on_moderation":
        messages.error(
            request,
            "Мероприятие находится на модерации. Редактирование станет доступно "
            "после того, как администратор одобрит или отклонит его.",
        )
        return redirect("partner:partner_event_list")

    # Проверяем, существует ли файл event.image, и если нет — сбрасываем
    if event.image:
        try:
            if not event.image.storage.exists(event.image.name):
                event.image.delete(save=False)
                event.image = None
                event.save(update_fields=["image"])
        except Exception:
            pass

    # Определяем primary_event_image для шаблона (доступно через request)
    primary_event_image = event.primary_image if event.pk else None
    request.primary_event_image = primary_event_image

    if event.has_sold_tickets:
        # Прямое редактирование закрыто — отправляем партнёра на форму заявки
        messages.warning(
            request,
            "Редактирование этого мероприятия запрещено, так как на него уже проданы билеты. "
            "Вы можете отправить заявку на изменение — администратор её рассмотрит.",
        )
        return redirect("partner:request_event_change", event_id=event.id)

    if request.method == "POST":
        # Передаем request.FILES, чтобы обработать загрузку нового видео
        # Определяем текущий пакет для передачи в форму
        current_package = event.package if event.package else (active_subscription.package if active_subscription else None)
        form = EventForm(request.POST, request.FILES, instance=event, current_package=current_package, request=request)

        # Удаляем старые файлы, если пришли новые
        new_video_file = request.FILES.get("video_url")
        if new_video_file and event.video_url:
            event.video_url.delete(save=False)

        new_image_file = request.FILES.get("image")
        if new_image_file and event.image:
            event.image.delete(save=False)

        # Очищаем медиафайлы (изображение, программа), если были отмечены флажки в форме
        for field_name in ["image", "program_file"]:
            clear_field_name = f"{field_name}-clear"
            if clear_field_name in request.POST:
                current_file = getattr(event, field_name)
                if current_file:
                    current_file.delete(save=False)
                setattr(event, field_name, None)

        if form.is_valid():
            # Проверяем типы загружаемых файлов
            error = _validate_event_files(request)
            if error:
                messages.error(request, error)
                return render(
                    request,
                    "partner/event_form.html",
                    _event_form_context(
                        request,
                        form,
                        is_edit=True,
                        ticket_data=_ticket_data_from_post(request, with_description=True),
                        selected_tag_ids=event.tags.values_list('id', flat=True),
                    ),
                )

            # Проверяем ограничения пакета на количество фотографий
            main_image = request.FILES.get("image")
            additional_images = request.FILES.getlist("images")

            # Считаем общее количество загружаемых фото
            total_images = (1 if main_image else 0) + len(additional_images)

            # Считаем уже существующие фото (если не заменяем основное)
            existing_images_count = 0
            if not main_image and event.image:
                existing_images_count += 1
            if not additional_images:
                existing_images_count += event.images.count()

            # Общее количество фото после загрузки
            final_images_count = existing_images_count + total_images

            # Проверяем не превышаем ли лимит пакета
            package = event.package if event.package else (active_subscription.package if active_subscription else None)
            if package and final_images_count > package.max_photos:
                additional_photos_allowed = package.max_photos - 1
                messages.error(
                    request,
                    f"Ваш пакет позволяет загрузить не более {package.max_photos} фотографий "
                    f"(1 основное + {additional_photos_allowed} дополнительных). "
                    f"Вы пытаетесь загрузить {final_images_count} фото."
                )
                return render(
                    request,
                    "partner/event_form.html",
                    _event_form_context(
                        request,
                        form,
                        is_edit=True,
                        ticket_data=_ticket_data_from_post(request),
                        selected_tag_ids=event.tags.values_list('id', flat=True),
                    ),
                )

            # Сохраняем форму
            event = form.save()

            # Основное фото (отдельный input image): если пришло — заменяем
            main_image = request.FILES.get("image")
            if main_image:
                event.image = main_image
                event.save(update_fields=["image"])
            elif request.POST.get("delete_main_image") == "1":
                # Старое основное фото (Event.image) помечено к удалению в форме
                if event.image:
                    event.image.delete(save=False)
                event.image = None
                event.save(update_fields=["image"])

            # Удаляем фотографии, которые были отмечены для удаления
            deleted_image_ids = request.POST.get("deleted_image_ids", "")
            if deleted_image_ids:
                for image_id in deleted_image_ids.split(","):
                    if image_id:
                        try:
                            image = EventImage.objects.get(id=int(image_id), event=event)
                            image.delete()
                        except EventImage.DoesNotExist:
                            pass

            # Обработка is_primary и новых фото (до добавления новых фото)
            primary_image_id = request.POST.get("primary_image_id", "")
            primary_new_index = request.POST.get("primary_new_photo_file_index", "")
            new_images = request.FILES.getlist("images")

            # Получаем текущее основное фото ДО изменений
            current_primary_id = event.images.filter(is_primary=True).values_list("id", flat=True).first()

            # Если пользователь не менял галочку — не трогаем is_primary
            if primary_image_id and str(primary_image_id) == str(current_primary_id):
                pass  # Галочка не изменилась, ничего не делаем
            else:
                # Снимаем is_primary со всех фото
                EventImage.objects.filter(event=event).update(is_primary=False)

                # Если выбрано существующее фото как основное
                if primary_image_id:
                    try:
                        img = EventImage.objects.get(id=int(primary_image_id), event=event)
                        img.is_primary = True
                        img.save(update_fields=["is_primary"])
                    except (EventImage.DoesNotExist, ValueError):
                        pass

            # Если выбрано новое загруженное фото как основное
            used_primary_index = None
            if primary_new_index and new_images:
                try:
                    idx = int(primary_new_index)
                    if 0 <= idx < len(new_images):
                        EventImage.objects.create(event=event, image=new_images[idx], is_primary=True)
                        used_primary_index = idx
                except (ValueError, IndexError):
                    pass
            elif new_images and not primary_image_id:
                # Если ни primary_image_id, ни primary_new_index не заданы, но есть новые фото — первое становится основным
                EventImage.objects.create(event=event, image=new_images[0], is_primary=True)
                used_primary_index = 0

            # Остальные новые фото (без is_primary)
            if new_images:
                for i, image in enumerate(new_images):
                    if i != used_primary_index:
                        EventImage.objects.create(event=event, image=image)

            # Если не выбрано конкретное фото как основное, но есть оставшиеся - делаем первое доступное фото основным
            if not primary_image_id and not primary_new_index:
                deleted_ids = [int(x) for x in deleted_image_ids.split(",") if x.strip()]

                # Проверяем, есть ли оставшиеся EventImage (исключая удалённые)
                if deleted_ids:
                    remaining_images = event.images.filter(is_primary=False).exclude(id__in=deleted_ids)
                else:
                    remaining_images = event.images.filter(is_primary=False)

                if remaining_images.exists():
                    # Делаем первое оставшееся фото основным
                    first_remaining = remaining_images.first()
                    first_remaining.is_primary = True
                    first_remaining.save(update_fields=["is_primary"])

            # Fallback: если основного фото нет ни после смен, ни после добавления —
            # назначаем первое оставшееся фото как основное (на случай если предыдущая логика не сработала)
            if not event.images.filter(is_primary=True).exists():
                first_available = event.images.first()
                if first_available:
                    first_available.is_primary = True
                    first_available.save(update_fields=["is_primary"])

            # Синхронизируем Event.image с primary EventImage
            event.set_primary_from_event_images()

            # Теги
            tags_ids = request.POST.getlist("tags")
            if tags_ids:
                selected_tags = tags_ids[:5]
                event.tags.set(selected_tags)

            # Билеты
            event.tickets.all().delete()
            rows = _parse_ticket_rows(request)

            if rows["has_free"] and rows["has_paid"]:
                messages.error(
                    request,
                    "Невозможно создать мероприятие с бесплатными и платными билетами одновременно.",
                )
                return render(
                    request,
                    "partner/event_form.html",
                    {
                        "form": form,
                        "is_edit": True,
                        "ticket_data": _ticket_data_from_post(request),
                        "rejection_messages": get_rejection_messages(request),
                        "all_tags": Tag.objects.all(),
                    },
                )

            _create_tickets(event, rows)

            return redirect("partner:partner_event_list")

    else:
        # GET: выводим пакет, который сейчас привязан к событию (event.package),
        # а также пакет из активной подписки пользователя (fallback),
        # чтобы информация всегда была доступна как в create_event.
        current_package = event.package if event.package else (active_subscription.package if active_subscription else None)
        form = EventForm(instance=event, current_package=current_package, request=request)

        # 1) Пакет события (если заполнен) — синхронизируем active_subscription с пакетом события
        if event.package:
            active_subscription = (
                UserPackageSubscription.objects.filter(
                    user=request.user,
                    package=event.package,
                    is_active=True,
                )
                .select_related("package")
                .first()
            )

        # 2) Fallback: активная подписка пользователя (как в create_event)
        fallback_subscription = (
            UserPackageSubscription.objects.filter(
                user=request.user,
                is_active=True,
            )
            .select_related("package")
            .first()
        )

        if fallback_subscription and not active_subscription:
            active_subscription = fallback_subscription

    return render(
        request,
        "partner/event_form.html",
        _event_form_context(
            request,
            form,
            is_edit=True,
            selected_tag_ids=event.tags.values_list('id', flat=True),
        ),
    )


@login_required
def partner_event_list(request):
    """
    Отображает список всех мероприятий текущего партнёра
    с разделением на актуальные и архивные + фильтрация.
    """
    # ---------- Параметры фильтрации ----------
    title_query = request.GET.get("title", None)
    date_query = request.GET.get("date", None)
    status_filter = request.GET.getlist("status")  # ['active'], ['archived'] или оба

    # ---------- Базовая выборка ----------
    events = Event.objects.filter(organizer=request.user)

    # ---------- Применяем фильтры ----------
    if title_query:
        events = events.filter(title__icontains=title_query)

    if date_query:
        try:
            query_date = datetime.fromisoformat(date_query)
            events = events.filter(date_time__date=query_date)
        except (ValueError, TypeError):
            pass

    # Сортировка (новые сверху)
    events = events.order_by("-date_time")

    # ---------- Разделяем на актуальные и архивные ----------
    now = timezone.now()

    def build_event_data(event_qs):
        """Формирует список словарей с продажами по каждому событию."""
        result = []
        for event in event_qs:
            sold_tickets = 0
            total = 0
            for ticket in event.tickets.all():
                sold = sum(
                    order.quantity
                    for order in ticket.orders.exclude(
                        payment_status__in=("canceled", "refunded")
                    )
                )
                sold_tickets += sold
                total += sold + ticket.available_quantity

            # Есть ли активная (pending) заявка на изменение по мероприятию
            pending_change_request = (
                event.change_requests.filter(status="pending").first()
                if event.has_sold_tickets
                else None
            )

            result.append({
                "event": event,
                "sold": sold_tickets,
                "total": total,
                "pending_change_request": pending_change_request,
            })
        return result

    active_qs = events.filter(date_time__gte=now)
    archived_qs = events.filter(date_time__lt=now)

    # ---------- Учитываем чекбоксы "Действующие" / "Истёкшие" ----------
    # Если ни один не выбран — показываем оба (поведение по умолчанию)
    show_active = not status_filter or "active" in status_filter
    show_archived = not status_filter or "archived" in status_filter

    active_events = build_event_data(active_qs) if show_active else []
    archived_events = build_event_data(archived_qs) if show_archived else []

    # ---------- Контекст ----------
    context = {
        "active_events": active_events,
        "archived_events": archived_events,
        "rejection_messages": get_rejection_messages(request),
    }
    return render(request, "partner/partner_event_list.html", context)


@login_required
def delete_event(request, event_id):
    """
    Удаляет мероприятие и связанные медиафайлы.
    """
    event = get_object_or_404(Event, id=event_id, organizer=request.user)

    if request.method == "POST":
        # Удаляем медиафайлы, если они существуют
        if event.image:
            event.image.delete()
        if event.video_url:
            event.video_url.delete()
        if event.program_file:
            event.program_file.delete()

        event.delete()
        return redirect("partner:partner_event_list")

    partner_profile = getattr(request.user, 'partner_profile', None)
    return render(
        request,
        "partner/event_confirm_delete.html",
        {"event": event, "partner_profile": partner_profile},
    )


@login_required
def bulk_delete_events(request):
    """
    Удаляет несколько мероприятий за раз.
    """
    if request.method == "POST":
        event_ids = request.POST.getlist("event_ids")
        if not event_ids:
            messages.error(request, "Не выбрано ни одного мероприятия для удаления.")
            return redirect("partner:partner_event_list")

        deleted_count = 0
        for event_id in event_ids:
            try:
                event = Event.objects.get(id=event_id, organizer=request.user)

                # Удаляем медиафайлы через storage backend
                if event.image:
                    event.image.delete()
                if event.video_url:
                    event.video_url.delete()
                if event.program_file:
                    event.program_file.delete()

                # Удаляем объект мероприятия
                event.delete()

                deleted_count += 1
            except Event.DoesNotExist:
                continue
            except Exception as e:
                logger.error("Ошибка при удалении мероприятия %s: %s", event_id, e)
                continue

        messages.success(request, f"Успешно удалено {deleted_count} мероприятий.")
        return redirect("partner:partner_event_list")

    return redirect("partner:partner_event_list")


@login_required
def check_video_status(request, event_id):
    """
    AJAX: возвращает статус обработки видео мероприятия.
    Используется фронтендом для polling во время обработки.
    """
    event = get_object_or_404(Event, id=event_id, organizer=request.user)

    return JsonResponse({
        "status": event.video_processing_status,
        "status_display": event.get_video_processing_status_display(),
    })


def _event_edit_blocked_response(event):
    """
    Проверяет, заблокировано ли изменение мероприятия (модерация или проданные билеты).
    Возвращает JsonResponse с ошибкой или None, если изменение разрешено.
    """
    if event.status == "on_moderation":
        return JsonResponse(
            {
                "status": "error",
                "message": "Мероприятие на модерации — изменение недоступно.",
            },
            status=403,
        )
    if event.has_sold_tickets:
        return JsonResponse(
            {
                "status": "error",
                "message": "На мероприятие проданы билеты — изменение недоступно. "
                           "Отправьте заявку на изменение.",
            },
            status=403,
        )
    return None


@login_required
def remove_media(request, media_type, media_id):
    """
    View для удаления медиафайлов через AJAX.
    media_id - это ID мероприятия (event_id) для image, video_url, program_file
    """
    if request.method != "POST":
        return JsonResponse(
            {"status": "error", "message": "Method not allowed"}, status=405
        )

    try:
        logger.info("remove_media: media_type=%s, media_id=%s, user=%s", media_type, media_id, request.user)

        if media_type in ["image", "video_url", "program_file"]:
            event = Event.objects.get(id=media_id, organizer=request.user)

            blocked = _event_edit_blocked_response(event)
            if blocked:
                return blocked

            field = media_type
            current_file = getattr(event, field, None)
            if current_file:
                logger.info("remove_media: удаляем %s=%s", field, current_file)
                event.delete_file_field(field)
                setattr(event, field, None)
                event.save()
                logger.info("remove_media: %s успешно удалён", field)
                return JsonResponse({"status": "success"})

            logger.warning("remove_media: файл %s не найден у мероприятия %s", media_type, media_id)
            return JsonResponse(
                {"status": "error", "message": "Media not found"}, status=404
            )

        elif media_type in ["video_business_card", "logo"]:
            profile = request.user.partner_profile
            if getattr(profile, media_type, None):
                profile.delete_file_field(media_type)
                setattr(profile, media_type, None)
                profile.save()
                return JsonResponse({"status": "success"})

        return JsonResponse(
            {"status": "error", "message": "Media not found"}, status=404
        )
    except Event.DoesNotExist:
        logger.error("remove_media: мероприятие %s не найдено", media_id)
        return JsonResponse(
            {"status": "error", "message": "Event not found"}, status=404
        )
    except Exception as e:
        logger.error("remove_media: ошибка: %s", e, exc_info=True)
        return JsonResponse({"status": "error", "message": str(e)}, status=500)


@login_required
def remove_event_image(request, image_id):
    """Удаление фотографии мероприятия через AJAX."""
    if request.method != "POST":
        return JsonResponse(
            {"status": "error", "message": "Method not allowed"}, status=405
        )

    try:
        image = EventImage.objects.get(id=image_id, event__organizer=request.user)
        event = image.event

        blocked = _event_edit_blocked_response(event)
        if blocked:
            return blocked

        # Если удаляемое фото было основным и совпадало с event.image — сбрасываем
        if image.is_primary and event.image and event.image.name == image.image.name:
            event.image = None

        image.delete_file_field("image")  # Корректное удаление из S3
        image.delete()  # Удаляем запись из БД

        # Если после удаления не осталось EventImage — сбрасываем event.image
        if not EventImage.objects.filter(event=event).exists():
            event.image = None
            event.save(update_fields=["image"])

        return JsonResponse({"status": "success"})
    except EventImage.DoesNotExist:
        return JsonResponse(
            {"status": "error", "message": "Image not found"}, status=404
        )
    except Exception as e:
        return JsonResponse({"status": "error", "message": str(e)}, status=500)


@login_required
def set_primary_image(request, image_id):
    """Установка основного фото мероприятия через AJAX."""
    if request.method != "POST":
        return JsonResponse(
            {"status": "error", "message": "Method not allowed"}, status=405
        )

    try:
        image = EventImage.objects.get(id=image_id, event__organizer=request.user)

        blocked = _event_edit_blocked_response(image.event)
        if blocked:
            return blocked

        # Снимаем is_primary у всех фото этого мероприятия
        EventImage.objects.filter(event=image.event).update(is_primary=False)
        image.is_primary = True
        image.save(update_fields=["is_primary"])

        # Также обновляем основное фото в модели Event
        event = image.event
        event.image = image.image
        event.save(update_fields=["image"])

        return JsonResponse({"status": "success"})
    except EventImage.DoesNotExist:
        return JsonResponse(
            {"status": "error", "message": "Image not found"}, status=404
        )
    except Exception as e:
        return JsonResponse({"status": "error", "message": str(e)}, status=500)


def send_partner_all_tickets_sold_notification(event):
    """
    Отправляет уведомление партнёру о том, что все билеты на мероприятие выкуплены.
    """
    subject = f"Все билеты на мероприятие '{event.title}' выкуплены"
    organizer_email = event.organizer.email

    # Формируем сообщение
    message = f"""
    <html>
    <body>
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <h2 style="color: #2c3e50;">Здравствуйте, {event.organizer.get_full_name()}!</h2>

            <p>Поздравляем! Все билеты на ваше мероприятие <strong>{event.title}</strong> были успешно выкуплены.</p>

            <div style="background-color: #f8f9fa; padding: 15px; border-radius: 5px; margin: 20px 0;">
                <p><strong>Дата и время:</strong> {event.date_time.strftime('%d.%m.%Y %H:%M')}</p>
                <p><strong>Место проведения:</strong> {event.get_place_address}</p>
            </div>

            <p>Теперь вы можете подготовиться к проведению мероприятия.</p>

            <div style="
                margin-top: 40px;
                padding-top: 20px;
                border-top: 1px solid #eee;
                font-size: 12px;
                color: #7f8c8d;
            ">
                <p>Если у вас возникли вопросы, обратитесь в нашу <a href="#">службу поддержки</a>.</p>
            </div>
        </div>
    </body>
    </html>
    """
    send_mail(
        subject,
        "",
        settings.DEFAULT_FROM_EMAIL,
        [organizer_email],
        html_message=message,
    )
