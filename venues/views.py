from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from .models import EquipmentItem
from django.views.generic import ListView, DetailView
from django.views.decorators.http import require_POST
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from .models import Venue, BookingRequest, EquipmentCategory, EquipmentItem
from .forms import BookingRequestForm
import json
# ФУНКЦИИ ДЛЯ АДМИНКИ 
@csrf_exempt
@login_required
def get_equipment_items(request):
    category_id = request.GET.get("category_id")
    if not category_id:
        return JsonResponse([], safe=False)

    items = EquipmentItem.objects.filter(category_id=category_id).values("id", "name")
    return JsonResponse(list(items), safe=False)

@csrf_exempt
@login_required
def save_venue_equipment(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)

    venue_id = request.POST.get('venue_id')
    equipment_id = request.POST.get('equipment_id')
    is_checked = request.POST.get('is_checked') == 'true'

    if not venue_id or not equipment_id:
        return JsonResponse({'success': False, 'error': 'Missing parameters'}, status=400)

    try:
        venue = Venue.objects.get(pk=venue_id)
        equipment = EquipmentItem.objects.get(pk=equipment_id)

        if is_checked:
            venue.equipment_items.add(equipment)
        else:
            venue.equipment_items.remove(equipment)

        return JsonResponse({'success': True})
    except Venue.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Venue not found'}, status=404)
    except EquipmentItem.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Equipment not found'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

@csrf_exempt
@login_required
def get_venue_equipment(request, venue_id):
    try:
        venue = Venue.objects.get(pk=venue_id)
        equipment_items = venue.equipment_items.values('id', 'name')
        return JsonResponse(list(equipment_items), safe=False)
    except Venue.DoesNotExist:
        return JsonResponse([], safe=False)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
    
    
# ПУБЛИЧНЫЕ ФУНКЦИИ
def public_get_equipment_items(request):
    """
    Публичный эндпоинт для получения списка оборудования.
    Используется для рендера чекбоксов в фильтре.
    """
    categories = EquipmentCategory.objects.prefetch_related('items').all()
    
    data = []
    for category in categories:
        items = [{'id': item.id, 'name': item.name} for item in category.items.all()]
        data.append({
            'category_id': category.id,
            'category_name': category.name,
            'items': items
        })
    
    return JsonResponse({'equipment': data})

def public_save_venue_equipment(request):
    """
    Публичный эндпоинт для применения фильтра.
    Принимает список ID оборудования и возвращает отрендеренный HTML плиток.
    """
    if request.method == 'POST':
        # Получаем список ID из тела запроса (JSON)
        try:
            data = json.loads(request.body)
            selected_item_ids = data.get('item_ids', [])
        except json.JSONDecodeError:
            selected_item_ids = request.POST.getlist('item_ids[]') # Альтернатива для form-data

        # Начинаем фильтрацию с опубликованных площадок
        venues = Venue.objects.filter(status='published')
        
        # Применяем фильтр по каждому выбранному item_id
        for item_id in selected_item_ids:
            venues = venues.filter(equipment_items__id=item_id)
        
        # Убираем дубликаты (если площадка подходит под несколько фильтров)
        venues = venues.distinct()

        # Рендерим карточки в HTML-строку
        html = render_to_string('venues/_venue_card.html', {'venues': venues})
        
        return JsonResponse({'html': html})

    return JsonResponse({'error': 'Invalid request'}, status=400)


class VenueListView(ListView):
    """
    Список площадок с фильтрацией и поэтапной подгрузкой.
    """

    model = Venue
    template_name = "venues/venue_list.html"
    context_object_name = "venues"
    paginate_by = 12  # Выводим 12 карточек за раз

    def get_queryset(self):

        qs = super().get_queryset().filter(status="published")

        # Фильтрация по GET-параметрам
        city = self.request.GET.get("city")
        if city:
            qs = qs.filter(city__iexact=city)
        else:
            qs = qs.filter(city__iexact="Новосибирск")
        
        # Фильтрация по оборудованию
        equipment_ids = self.request.GET.getlist("equipment")
        if equipment_ids:
            for equipment_id in equipment_ids:
                qs = qs.filter(equipment_items__id=equipment_id)

        district = self.request.GET.get("district")
        if district:
            qs = qs.filter(district__iexact=district)

        metro = self.request.GET.get("metro")
        if metro:
            qs = qs.filter(metro__iexact=metro)

        venue_type = self.request.GET.get("venue_type")
        if venue_type:
            qs = qs.filter(venue_type=venue_type)

        max_capacity = self.request.GET.get("max_capacity")
        if max_capacity and max_capacity.isdigit():
            qs = qs.filter(max_capacity__gte=max_capacity)

        price = self.request.GET.get("price")
        if price and price.isdigit():
            qs = qs.filter(price__lte=price)

        price_unit = self.request.GET.get("price_unit")
        if price_unit:
            qs = qs.filter(price_unit=price_unit)

        venue_formats = self.request.GET.getlist("venue_format")
        if venue_formats:
            # Заменяем "+" на пробелы в значениях форматов
            normalized_formats = [vf.replace('+', ' ') for vf in venue_formats]
            qs = qs.filter(formats__name__in=normalized_formats)

        # Обработка параметра сортировки
        sort_param = self.request.GET.get("sort")

        # Сортировка по приоритету тарифа и другим параметрам
        from django.db.models import Case, When, Value, IntegerField, F

        qs = qs.annotate(
            tariff_priority=Case(
                When(tariff=3, then=Value(3)),
                When(tariff=2, then=Value(2)),
                When(tariff=1, then=Value(1)),
                default=Value(0),
                output_field=IntegerField(),
            )
        )

        # Применяем сортировку в зависимости от параметра
        if sort_param == "relevance" or not sort_param:
            # Сортировка по релевантности (по умолчанию: приоритет тарифа и цена)
            qs = qs.order_by("-tariff_priority", "price")
        elif sort_param == "price_asc":
            # Цена по возрастанию
            qs = qs.order_by("price", "-tariff_priority")
        elif sort_param == "price_desc":
            # Цена по убыванию
            qs = qs.order_by("-price", "-tariff_priority")
        elif sort_param == "area":
            # Площадь (чем больше, тем выше в списке)
            qs = qs.order_by("-area", "-tariff_priority")
        elif sort_param == "capacity":
            # Вместимость (чем больше, тем выше в списке)
            qs = qs.order_by("-max_capacity", "-tariff_priority")
        elif sort_param == "venue_type":
            # Тип помещения
            qs = qs.order_by("venue_type__name", "-tariff_priority")
        elif sort_param == "priority":
            # Приоритет размещения (тариф)
            qs = qs.order_by("-tariff_priority")

        return qs.distinct()

    def post(self, request, *args, **kwargs):
        venue_id = request.POST.get("venue_id")
        venue = get_object_or_404(Venue, id=venue_id)

        form = BookingRequestForm(request.POST)
        if form.is_valid():
            booking_request = form.save(commit=False)
            booking_request.venue = venue
            booking_request.save()
            return self.get(request, *args, **kwargs)

        # Если форма невалидна, возвращаем ту же страницу с ошибками
        return self.get(request, *args, **kwargs)

@require_POST
def send_booking_request(request):
    """
    Обработка формы заявки через AJAX.
    """
    form = BookingRequestForm(request.POST)

    if form.is_valid():
        booking_request = form.save()

        # Здесь можно добавить отправку email администратору или владельцу площадки

        return JsonResponse({"success": True})

    return JsonResponse({"success": False, "errors": form.errors})


class VenueDetailView(DetailView):
    """
    Отображает подробную информацию об одной площадке.
    """

    model = Venue  
    template_name = "venues/venue_detail.html"  
    context_object_name = "venue" 

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        venue = self.object
        context["limits"] = venue.TARIFF_LIMITS.get(venue.tariff, {})
        return context
