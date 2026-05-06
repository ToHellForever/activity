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
    template_name = "venues/venue_list.html"
    context_object_name = "venues"
    paginate_by = 12  # Выводим 12 карточек за раз

    def get_queryset(self):
        # Debug output for filter values
        print("GET parameters:", self.request.GET)
        print("has_parking:", self.request.GET.get("has_parking"))
        print("has_wifi:", self.request.GET.get("has_wifi"))

        qs = super().get_queryset().filter(status="published")

        # Фильтрация по GET-параметрам
        city = self.request.GET.get("city")
        if city:
            qs = qs.filter(city__iexact=city)
        else:
            qs = qs.filter(city__iexact="Новосибирск")  # По умолчанию Новосибирск

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

        equipment = self.request.GET.get("equipment")
        if equipment:
            qs = qs.filter(equipment__name__iexact=equipment)

        has_parking = self.request.GET.get("has_parking")
        if has_parking == "on":
            qs = qs.filter(parking=True)
        elif has_parking == "off":
            qs = qs.filter(parking=False)

        has_wifi = self.request.GET.get("has_wifi")
        if has_wifi == "on":
            qs = qs.filter(has_wifi=True)
        elif has_wifi == "off":
            qs = qs.filter(has_wifi=False)

        venue_format = self.request.GET.get("venue_format")
        if venue_format:
            qs = qs.filter(formats__name__iexact=venue_format)

        # Сортировка по приоритету тарифа и другим параметрам
        from django.db.models import Case, When, Value, IntegerField

        qs = qs.annotate(
            tariff_priority=Case(
                When(tariff=3, then=Value(3)),
                When(tariff=2, then=Value(2)),
                When(tariff=1, then=Value(1)),
                default=Value(0),
                output_field=IntegerField(),
            )
        ).order_by("-tariff_priority", "price")

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


class VenueDetailView(DetailView):
    """
    Карточка площадки.
    """

    model = Venue
    template_name = "venues/venue_detail.html"
    context_object_name = "venue"


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

    model = Venue  # Указываем, с какой моделью работаем
    template_name = "venues/venue_detail.html"  # Указываем шаблон
    context_object_name = "venue"  # Как переменная будет называться в шаблоне

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        venue = self.object
        context["limits"] = venue.TARIFF_LIMITS.get(venue.tariff, {})
        return context
