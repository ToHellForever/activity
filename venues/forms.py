from django import forms
from .models import Venue, BookingRequest


class VenueForm(forms.ModelForm):
    class Meta:
        model = Venue
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Перемещаем поле tariff в начало
        if "tariff" in self.fields:
            # Сохраняем поле тарифа
            tariff_field = self.fields.pop("tariff")
            # Вставляем его первым
            self.fields = {"tariff": tariff_field, **self.fields}


class BookingRequestForm(forms.ModelForm):
    class Meta:
        model = BookingRequest
        fields = "__all__"
