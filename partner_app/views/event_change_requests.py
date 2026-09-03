"""Заявки на изменение мероприятия (когда прямое редактирование закрыто)."""
import logging

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.utils import timezone

from core.models import (
    Event,
    EventImage,
    UserPackageSubscription,
)
from ..forms import EventForm
from ..models import EventChangeRequest, EventChangeRequestImage
from .decorators import check_partner_status, get_rejection_messages
from .events import (
    _event_form_context,
    _ticket_data_from_post,
    _validate_event_files,
    _parse_ticket_rows,
)

logger = logging.getLogger(__name__)

# Поля Event, значения которых сохраняются в JSON diff
# 'package' намеренно исключён: форма всегда отправляет текущий пакет из подписки
# через hidden-поле в шаблоне, что вызывает ложные срабатывания.
SERIALIZABLE_FIELDS = [
    "title",
    "description",
    "date_time",
    "place_data",
    "category",
    "format",
    "allow_booking_without_payment",
    "auto_close_sales_hours",
    "refund_deadline_hours",
    "duration",
    "allow_platform_requests",
    "additional_adress",
    "requires_strict_moderation",
]


def _serialize_value(value):
    """Приводит значение поля Event к JSON-сериализуемому виду."""
    if value is None or value == "":
        return None
    if hasattr(value, "pk"):
        return value.pk
    if hasattr(value, "isoformat"):
        if hasattr(value, "hour"):
            value = value.replace(microsecond=0, second=0)
        return value.isoformat()
    if hasattr(value, "quantize"):  # Decimal
        return str(value)
    return value


def _snapshot_event(event):
    """
    Снимок исходных значений полей мероприятия.
    Нужен ДО валидации формы: ModelForm.full_clean мутирует form.instance,
    поэтому сравнивать очищенные данные нужно с исходным снимком.
    """
    return {field_name: getattr(event, field_name, None) for field_name in SERIALIZABLE_FIELDS}


def _build_changes_dict(form, original):
    """Сравнивает очищенные данные формы с исходным снимком мероприятия и возвращает diff."""
    changes = {}
    for field_name in SERIALIZABLE_FIELDS:
        if field_name not in form.cleaned_data:
            continue
        new_value = form.cleaned_data[field_name]

        # Пропускаем пустые/отменённые значения — это не намеренные изменения
        if new_value is None or new_value == "" or new_value == "off" or new_value is False:
            continue
        if hasattr(new_value, "pk") and new_value.pk is None:
            continue

        current_value = original.get(field_name)
        if _serialize_value(new_value) != _serialize_value(current_value):
            changes[field_name] = _serialize_value(new_value)
    return changes


def _save_gallery_new_images(change_request, request):
    """Сохраняет загруженные новые фото галереи и флаг основного."""
    new_images = request.FILES.getlist("images")
    created = []
    for image in new_images:
        created.append(
            EventChangeRequestImage.objects.create(
                change_request=change_request, image=image
            )
        )

    primary_new_index = request.POST.get("primary_new_photo_file_index", "")
    if primary_new_index and created:
        try:
            idx = int(primary_new_index)
            if 0 <= idx < len(created):
                created[idx].is_primary = True
                created[idx].save(update_fields=["is_primary"])
        except (ValueError, IndexError):
            pass


def _is_only_primary_photo_change(request, change_request, event):
    """
    Проверяет, является ли изменение ТОЛЬКО сменой главного фото среди существующих.
    Если да — применяется сразу, без модерации.
    """
    # Есть ли только primary_image_id (смена главного фото)
    if not change_request.primary_image_id:
        return False

    # Проверяем, что нет других изменений
    if change_request.changes:
        return False
    if change_request.tickets_data:
        return False
    if change_request.tag_ids:
        return False
    if change_request.new_image:
        return False
    if change_request.new_video_url:
        return False
    if change_request.new_program_file:
        return False
    if change_request.clear_image:
        return False
    if change_request.clear_video_url:
        return False
    if change_request.clear_program_file:
        return False
    if change_request.delete_image_ids:
        return False
    if change_request.primary_new_image_index is not None:
        return False
    # Проверяем загруженные новые фото по FILES, а не по relationship
    new_images = request.FILES.getlist("images")
    if new_images:
        return False

    # Проверяем, что новое главное фото отличается от текущего
    current_primary = event.primary_image
    if current_primary and current_primary.id == change_request.primary_image_id:
        # Галочка не поменялась — изменений нет
        return False

    return True


def _apply_primary_photo_change(change_request, event):
    """
    Применяет смену главного фото среди существующих (без модерации).
    """
    from core.models import EventImage

    new_primary = EventImage.objects.filter(
        event=event, id=change_request.primary_image_id
    ).first()

    if not new_primary:
        return

    # Снимаем флаг is_primary со старого главного фото
    old_primary = event.images.filter(is_primary=True).first()
    if old_primary:
        old_primary.is_primary = False
        old_primary.save(update_fields=["is_primary"])

    # Устанавливаем новое главное фото
    new_primary.is_primary = True
    new_primary.save(update_fields=["is_primary"])


@login_required
@check_partner_status('can_create_events')
def request_event_change(request, event_id):
    """
    Форма заявки на изменение мероприятия.

    Доступна, когда мероприятие активно и на него продан хотя бы 1 билет
    (прямое редактирование закрыто). Изменения не применяются сразу,
    а сохраняются как заявка на рассмотрение администратору.
    """
    event = get_object_or_404(Event, id=event_id, organizer=request.user)

    # Мероприятие на модерации — редактирование закрыто полностью
    if event.status == "on_moderation":
        messages.error(
            request,
            "Мероприятие находится на модерации. Редактирование станет доступно "
            "после того, как администратор одобрит или отклонит его.",
        )
        return redirect("partner:partner_event_list")

    # Прямое редактирование разрешено — отправляем в обычную форму
    if not event.has_sold_tickets:
        return redirect("partner:edit_event", event_id=event.id)

    pending_request = EventChangeRequest.objects.filter(
        event=event, status="pending"
    ).first()

    if pending_request:
        messages.warning(
            request,
            "По этому мероприятию уже отправлена заявка на изменение, "
            "она находится на рассмотрении администратора.",
        )
        return redirect("partner:partner_event_list")

    active_subscription = (
        UserPackageSubscription.objects.filter(user=request.user, is_active=True)
        .select_related("package")
        .first()
    )

    if request.method == "POST":
        current_package = (
            event.package
            if event.package
            else (active_subscription.package if active_subscription else None)
        )
        # Снимок исходных значений — ДО создания формы (EventForm.__init__ через
        # construct_instance мутирует instance, искажая снимок)
        original = _snapshot_event(event)

        form = EventForm(
            request.POST,
            request.FILES,
            instance=event,
            current_package=current_package,
            request=request,
        )

        if form.is_valid():
            error = _validate_event_files(request)
            if error:
                messages.error(request, error)
                return render(
                    request,
                    "partner/event_form.html",
                    _change_request_context(request, event, form),
                )

            rows = _parse_ticket_rows(request)
            if rows["has_free"] and rows["has_paid"]:
                messages.error(
                    request,
                    "Невозможно создать мероприятие с бесплатными и платными билетами одновременно.",
                )
                return render(
                    request,
                    "partner/event_form.html",
                    _change_request_context(
                        request,
                        event,
                        form,
                        ticket_data=_ticket_data_from_post(request, with_description=True),
                    ),
                )

            change_request = EventChangeRequest(event=event, partner=request.user)

            # Diff обычных полей
            change_request.changes = _build_changes_dict(form, original)

            # Теги: сохраняем только если список отличается от текущего
            tags_ids = request.POST.getlist("tags")
            proposed_tag_ids = sorted(int(t) for t in tags_ids if t.isdigit())
            current_tag_ids = sorted(event.tags.values_list("id", flat=True))
            if proposed_tag_ids != current_tag_ids:
                change_request.tag_ids = proposed_tag_ids

            # Билеты: сохраняем только если список отличается от текущего
            names = rows["names"]
            proposed_tickets = []
            for i, name in enumerate(names):
                price = rows["prices"][i] if i < len(rows["prices"]) else ""
                quantity = rows["quantities"][i] if i < len(rows["quantities"]) else ""
                description = rows["descriptions"][i] if i < len(rows["descriptions"]) else ""
                is_per_person = rows["is_per_person"][i] if i < len(rows["is_per_person"]) else ""
                min_quantity = rows["min_quantities"][i] if i < len(rows["min_quantities"]) else ""
                if name and price and quantity:
                    proposed_tickets.append(
                        {
                            "name": name,
                            "price": str(price),
                            "quantity": str(quantity),
                            "description": description,
                            "is_per_person": "on" if is_per_person else "",
                            "min_quantity": str(min_quantity),
                        }
                    )
            current_tickets = [
                {
                    "name": t.name,
                    "price": str(int(float(str(t.price)))),  # Нормализуем: Decimal -> int -> str
                    "quantity": str(t.available_quantity),
                    "description": t.ticket_description or "",
                    "is_per_person": "on" if t.is_per_person else "",
                    "min_quantity": str(t.min_quantity),
                }
                for t in event.tickets.all()
            ]

            # Нормализуем proposed_tickets: если поле содержит пустую строку,
            # заменяем на значение из current_tickets (если есть такой же билет).
            # Это нужно, потому что форма может не отправлять все поля
            # (например, min_quantity, is_per_person), и они придут как "".
            current_by_name = {}
            for t in current_tickets:
                current_by_name[t["name"]] = dict(t)
            for pt in proposed_tickets:
                ct = current_by_name.get(pt["name"])
                if ct:
                    for key in ("is_per_person", "min_quantity", "description"):
                        if pt.get(key) == "" and key in ct:
                            pt[key] = ct[key]

            # Сравниваем как отсортированные кортежи для надёжности
            proposed_sorted = sorted([tuple(sorted(d.items())) for d in proposed_tickets])
            current_sorted = sorted([tuple(sorted(d.items())) for d in current_tickets])
            if proposed_sorted != current_sorted:
                change_request.tickets_data = proposed_tickets

            # Медиафайлы
            main_image = request.FILES.get("image")
            if main_image:
                change_request.new_image = main_image
            video_file = request.FILES.get("video_url")
            if video_file:
                change_request.new_video_url = video_file
            program_file = request.FILES.get("program_file")
            if program_file:
                change_request.new_program_file = program_file

            change_request.clear_image = request.POST.get("delete_main_image") == "1"
            change_request.clear_video_url = request.POST.get("clear_video_url") == "1" or "video_url-clear" in request.POST
            change_request.clear_program_file = request.POST.get("clear_program_file") == "1" or "program_file-clear" in request.POST

            # Галерея: заполняем поля ДО save() — иначе не сохранятся в БД
            deleted_image_ids = request.POST.get("deleted_image_ids", "")
            change_request.delete_image_ids = [
                int(x) for x in deleted_image_ids.split(",") if x.strip().isdigit()
            ]

            primary_image_id = request.POST.get("primary_image_id", "")
            change_request.primary_image_id = (
                int(primary_image_id) if primary_image_id.isdigit() else None
            )

            primary_new_index = request.POST.get("primary_new_photo_file_index", "")
            if primary_new_index and primary_new_index.isdigit():
                change_request.primary_new_image_index = int(primary_new_index)

            # === Проверяем: только ли смена главного фото среди существующих ===
            # Если да — применяем сразу, без модерации
            if _is_only_primary_photo_change(request, change_request, event):
                _apply_primary_photo_change(change_request, event)
                messages.success(
                    request,
                    "Изменения применены.",
                )
                return redirect("partner:partner_event_list")

            try:
                with transaction.atomic():
                    change_request.full_clean()
                    change_request.save()

                    # Сохраняем загруженные новые фото галереи (нужно после save)
                    new_images = request.FILES.getlist("images")
                    created = []
                    for image in new_images:
                        created.append(
                            EventChangeRequestImage.objects.create(
                                change_request=change_request, image=image
                            )
                        )

                    if change_request.primary_new_image_index is not None and created:
                        try:
                            idx = change_request.primary_new_image_index
                            if 0 <= idx < len(created):
                                created[idx].is_primary = True
                                created[idx].save(update_fields=["is_primary"])
                        except (ValueError, IndexError):
                            pass

            except Exception as e:
                logger.error("Ошибка сохранения заявки на изменение: %s", e, exc_info=True)
                messages.error(
                    request,
                    "Не удалось сохранить заявку. Возможно, по этому мероприятию "
                    "уже есть заявка на рассмотрении.",
                )
                return redirect("partner:partner_event_list")

            if not change_request.has_changes:
                change_request.delete()
                messages.info(
                    request,
                    "Вы не предложили никаких изменений — заявка не создана.",
                )
                return redirect("partner:partner_event_list")

            messages.success(
                request,
                "Заявка на изменение отправлена администратору. "
                "Изменения будут применены после одобрения.",
            )
            return redirect("partner:partner_event_list")

    else:
        current_package = (
            event.package
            if event.package
            else (active_subscription.package if active_subscription else None)
        )
        form = EventForm(instance=event, current_package=current_package, request=request)

    return render(
        request,
        "partner/event_form.html",
        _change_request_context(request, event, form),
    )


def _change_request_context(request, event, form, ticket_data=None):
    """Контекст для рендера event_form.html в режиме заявки на изменение."""
    context = _event_form_context(
        request,
        form,
        is_edit=True,
        ticket_data=ticket_data,
        selected_tag_ids=event.tags.values_list("id", flat=True),
        primary_event_image=event.primary_image if event.pk else None,
    )
    context["is_change_request"] = True
    context["change_request_event"] = event
    return context

