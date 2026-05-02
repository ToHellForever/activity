from django.views.generic import ListView, DetailView
from django.views.decorators.http import require_POST
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from .models import Venue, BookingRequest
from .forms import BookingRequestForm

class VenueListView(ListView):
    """
    Список площадок с фильтрацией и поэтапной подгрузкой.
    """
    model = Venue
    template_name = 'venues/venue_list.html'
    context_object_name = 'venues'
    paginate_by = 12  # Выводим 12 карточек за раз

    def get_queryset(self):
        qs = super().get_queryset().filter(status='published')

        # Фильтрация по GET-параметрам из ТЗ
        city = self.request.GET.get('city')
        if city:
            qs = qs.filter(city__iexact=city)

        district = self.request.GET.get('district')
        if district:
            qs = qs.filter(district__iexact=district)

        metro = self.request.GET.get('metro')
        if metro:
            qs = qs.filter(metro__iexact=metro)

        venue_type_id = self.request.GET.get('type')
        if venue_type_id:
            qs = qs.filter(venue_type_id=venue_type_id)

        max_capacity = self.request.GET.get('max_capacity')
        if max_capacity and max_capacity.isdigit():
            qs = qs.filter(max_capacity__gte=max_capacity)

        price_from = self.request.GET.get('price_from')
        if price_from and price_from.isdigit():
            qs = qs.filter(price__gte=price_from)

        price_to = self.request.GET.get('price_to')
        if price_to and price_to.isdigit():
            qs = qs.filter(price__lte=price_to)

        has_parking = self.request.GET.get('parking')
        if has_parking == 'on':
            qs = qs.filter(parking=True)

        has_wifi_queryset_ids = self.request.GET.getlist('has_wifi') # Пример для оборудования/удобств

        # Сортировка по приоритету тарифа и другим параметрам (пример)
        qs = qs.order_by('-placement_tariff', 'price')

        return qs

    def post(self, request, *args, **kwargs):
        venue_id = request.POST.get('venue_id')
        venue = get_object_or_404(Venue, id=venue_id)

        form = BookingRequestForm(request.POST)
        if form.is_valid():
            booking_request = form.save(commit=False)
            booking_request.venue = venue
            booking_request.save()
            return self.get(request, *args, **kwargs)

        # Если форма невалидна, возвращаем ту же страницу с ошибками
        return self.get(request, *args, **kwargs)

class VenueDetailView(DetailView):
    """
    Карточка площадки.
    """
    model = Venue
    template_name = 'venues/venue_detail.html'
    context_object_name = 'venue'
    
@require_POST
def send_booking_request(request):
    """
    Обработка формы заявки через AJAX.
    """
    form = BookingRequestForm(request.POST)
    
    if form.is_valid():
        booking_request = form.save()
        
        # Здесь можно добавить отправку email администратору или владельцу площадки
        
        return JsonResponse({'success': True})
        
    return JsonResponse({'success': False, 'errors': form.errors})



class VenueDetailView(DetailView):
    """
    Отображает подробную информацию об одной площадке.
    """
    model = Venue  # Указываем, с какой моделью работаем
    template_name = 'venues/venue_detail.html' # Указываем шаблон
    context_object_name = 'venue' # Как переменная будет называться в шаблоне

    def get_queryset(self):
        # Показываем только опубликованные площадки
        return Venue.objects.filter(status='published')