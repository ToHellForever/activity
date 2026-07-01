from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from django.forms import ClearableFileInput, MultipleChoiceField, CheckboxSelectMultiple
from django.utils import timezone
import re
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

        # Обработка видимости полей в зависимости от тарифа
        if "tariff" in self.fields and "full_description" in self.fields:
            # Получаем текущее значение тарифа
            initial_tariff = self.initial.get("tariff", None)
            
            # Если тариф Free (1), скрываем поле полного описания
            if initial_tariff == 1:
                self.fields["full_description"].widget = forms.HiddenInput()
                self.fields["full_description"].required = False

    def clean_full_description(self):
        full_description = self.cleaned_data.get("full_description")
        tariff = self.cleaned_data.get("tariff")

        if full_description and tariff:
            # Проверяем только для тарифов Standard и Premium
            if tariff == 1:  # Для Free тарифа полное описание не обязательно
                return full_description

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
    def __init__(self, *args, **kwargs):
        self.venue = kwargs.pop("venue", None)
        super().__init__(*args, **kwargs)

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
        widgets = {
            "email": forms.EmailInput(attrs={"required": "required"}),
            "name": forms.TextInput(attrs={"required": "required"}),
            "phone": forms.TextInput(attrs={"required": "required"}),
            "event_date": forms.DateTimeInput(attrs={"required": "required"}),
            "participants_count": forms.NumberInput(attrs={"required": "required"}),
            "event_format": forms.TextInput(attrs={"required": "required"}),
        }

    def clean_event_date(self):
        event_date = self.cleaned_data.get("event_date")
        if event_date:
            now = timezone.now()
            # Запрещаем выбирать сегодняшнюю и прошедшие даты
            if event_date.date() <= now.date():
                raise ValidationError(
                    "Дата мероприятия должна быть будущей (завтра или позже)"
                )
        return event_date

    def clean_phone(self):
        phone = self.cleaned_data.get("phone")
        if phone:
            # Удаляем все нецифровые символы кроме возможного + в начале
            cleaned_phone = phone
            if phone.startswith("+"):
                cleaned_phone = "+" + re.sub(r"\D", "", phone[1:])
            else:
                cleaned_phone = re.sub(r"\D", "", phone)

            # Проверка формата российского номера
            if phone.startswith("+"):
                # Для международного формата (+7...) проверяем общую длину
                if len(cleaned_phone) != 12:  # +7 и 10 цифр номера
                    raise ValidationError(
                        "Номер телефона должен быть в формате +7XXXXXXXXXX (11 цифр после +)"
                    )
            else:
                # Для местного формата проверяем 11 цифр (начинается с 7 или 8)
                if len(cleaned_phone) != 11 or (
                    cleaned_phone[0] != "7" and cleaned_phone[0] != "8"
                ):
                    raise ValidationError(
                        "Номер телефона должен содержать 11 цифр и начинаться с 7 или 8"
                    )

            # Сохраняем очищенный номер
            self.cleaned_data["phone"] = cleaned_phone
        return phone

    def clean_participants_count(self):
        participants_count = self.cleaned_data.get("participants_count")
        if (
            self.venue
            and participants_count
            and participants_count > self.venue.max_capacity
        ):
            raise ValidationError(
                f"Количество участников не может превышать {self.venue.max_capacity} - максимальную вместимость площадки"
            )
        return participants_count
