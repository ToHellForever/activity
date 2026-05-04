from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
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

    def clean_full_description(self):
        full_description = self.cleaned_data.get("full_description")
        tariff = self.cleaned_data.get("tariff")

        if full_description and tariff:
            limits = Venue.TARIFF_LIMITS.get(tariff, {})
            description_limit = limits.get("description_limit", 500)

            if len(full_description) > description_limit:
                raise ValidationError(
                    _(
                        "Максимальная длина описания для тарифа %(tariff)s - %(limit)s символов. Ваше описание содержит %(length)s символов."
                    )
                    % {
                        "tariff": tariff,
                        "limit": description_limit,
                        "length": len(full_description),
                    }
                )

        return full_description

    def clean(self):
        cleaned_data = super().clean()
        tariff = cleaned_data.get("tariff")
        images = cleaned_data.get("images")
        video = cleaned_data.get("video")

        if tariff:
            limits = Venue.TARIFF_LIMITS.get(tariff, {})

            # Проверка количества фотографий (пока только главное фото, но логика готова для расширения)
            max_photos = limits.get("max_photos", 1)
            if images and max_photos < 1:
                raise ValidationError(
                    _("Для тарифа %(tariff)s загрузка фотографий не разрешена.")
                    % {"tariff": tariff}
                )

            # Проверка возможности загрузки видео
            has_video = limits.get("has_video", False)
            if video and not has_video:
                raise ValidationError(
                    _("Для тарифа %(tariff)s загрузка видео не разрешена.")
                    % {"tariff": tariff}
                )

        return cleaned_data


class BookingRequestForm(forms.ModelForm):
    class Meta:
        model = BookingRequest
        fields = "__all__"
