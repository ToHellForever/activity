from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from django.forms import ClearableFileInput, MultipleChoiceField, CheckboxSelectMultiple
from .models import Venue, BookingRequest, VenueImage


class MultipleFileInput(ClearableFileInput):
    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("widget", MultipleFileInput())
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        single_file_clean = super().clean
        if isinstance(data, (list, tuple)):
            result = [single_file_clean(d, initial) for d in data]
        else:
            result = single_file_clean(data, initial)
        return result


class VenueImageForm(forms.ModelForm):
    images = MultipleFileField(label="Фотографии", required=False)

    class Meta:
        model = VenueImage
        fields = []  # Не отображаем поле image в форме, так как используем images

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Скрываем стандартное поле image, так как используем кастомное images
        if "image" in self.fields:
            self.fields["image"].widget = forms.HiddenInput()

    def save(self, commit=True):
        # Базовая логика сохранения без обработки images
        instance = super().save(commit=False)
        if commit:
            instance.save()
            self.save_m2m()
        return instance

    def save_m2m(self):
        # Пустой метод, так как обработка images происходит в админке
        pass


class VenueForm(forms.ModelForm):
    class Meta:
        model = Venue
        fields = "__all__"
        widgets = {
            "formats": forms.CheckboxSelectMultiple,
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Перемещаем поле tariff в начало
        if "tariff" in self.fields:
            # Сохраняем поле тарифа
            tariff_field = self.fields.pop("tariff")
            # Вставляем его первым
            self.fields = {"tariff": tariff_field, **self.fields}

    def clean_short_description(self):
        short_description = self.cleaned_data.get("short_description")
        tariff = self.cleaned_data.get("tariff")

        if short_description and tariff:
            # Для Free тарифа краткое описание ограничено 500 символами
            if tariff == 1 and len(short_description) > 500:
                raise ValidationError(
                    _(
                        "Максимальная длина краткого описания для тарифа Free - 500 символов."
                    )
                )

        return short_description

    def clean_full_description(self):
        full_description = self.cleaned_data.get("full_description")
        tariff = self.cleaned_data.get("tariff")

        if full_description and tariff:
            limits = Venue.TARIFF_LIMITS.get(tariff, {})
            description_limit = limits.get("description_limit", 500)

            if len(full_description) > description_limit:
                tariff_name = dict(Venue.TARIFF_CHOICES).get(tariff, str(tariff))
                raise ValidationError(
                    _(
                        "Максимальная длина описания для тарифа %(tariff)s - %(limit)s символов. Ваше описание содержит %(length)s символов."
                    )
                    % {
                        "tariff": tariff_name,
                        "limit": description_limit,
                        "length": len(full_description),
                    }
                )

        return full_description

    def clean(self):
        cleaned_data = super().clean()
        tariff = cleaned_data.get("tariff")
        video = cleaned_data.get("video")

        if tariff:
            limits = Venue.TARIFF_LIMITS.get(tariff, {})

            # Проверка возможности загрузки видео
            has_video = limits.get("has_video", False)
            if video and not has_video:
                tariff_name = dict(Venue.TARIFF_CHOICES).get(tariff, str(tariff))
                raise ValidationError(
                    _("Для тарифа %(tariff)s загрузка видео не разрешена.")
                    % {"tariff": tariff_name}
                )

        return cleaned_data


class BookingRequestForm(forms.ModelForm):
    class Meta:
        model = BookingRequest
        fields = [
            "name",
            "phone",
            "email",
            "event_date",
            "participants_count",
            "event_format",
            "comment",
        ]
