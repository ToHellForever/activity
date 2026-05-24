from django import forms
from django.contrib.auth import get_user_model
from core.models import Event, PartnerDocument, PayoutDetails, EventPackage, Tag
from .models import ReportSchedule
User = get_user_model()


class EventForm(forms.ModelForm):
    """
    Форма для создания и редактирования мероприятия.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Делаем поля обязательными
        self.fields["title"].required = True
        self.fields["description_short"].required = True
        self.fields["description_full"].required = True
        self.fields["date_time"].required = True
        self.fields["place_data"].required = False
        self.fields["image"].required = True
        self.fields["refund_deadline_hours"].required = True
        self.fields["duration"].required = False

        # Настройка поля auto_close_sales_hours
        self.fields["auto_close_sales_hours"].required = True
        self.fields["auto_close_sales_hours"].widget.attrs["min"] = 24
        self.fields["auto_close_sales_hours"].help_text = "Продажи автоматически будут прекращены за указанное количество часов до начала мероприятия (минимум 24 часа)."

        # Кастомные сообщения об ошибках
        self.fields["date_time"].error_messages = {
            "required": "Пожалуйста, укажите дату и время проведения мероприятия."
        }

    def clean_duration(self):
        duration = self.cleaned_data.get("duration")
        if duration:
            try:
                hours, minutes = map(int, duration.split(":"))
                if hours < 0 or minutes < 0 or minutes >= 60:
                    raise ValueError("Некорректное значение")
                return duration
            except Exception:
                raise forms.ValidationError(
                    "Неверный формат. Используйте ЧЧ:ММ (например, 02:30)"
                )
        return None

    def clean_auto_close_sales_hours(self):
        auto_close_sales_hours = self.cleaned_data.get("auto_close_sales_hours")
        if auto_close_sales_hours is not None and auto_close_sales_hours < 24:
            raise forms.ValidationError("Минимальное значение — 24 часа.")
        return auto_close_sales_hours

    def clean(self):
        cleaned_data = super().clean()
        package = cleaned_data.get("package")
        image = cleaned_data.get("image")
        video_url = cleaned_data.get("video_url")
        program_file = cleaned_data.get("program_file")

        if package:
            # Проверка на количество фотографий
            if package.max_photos == 1 and image and hasattr(image, 'file'):
                # Для пакета "Старт" можно загрузить только 1 фото
                pass  # Пока просто пропускаем, так как ограничение на 1 фото уже есть в модели пакета

            # Проверка на наличие видео
            if not package.has_video and video_url:
                raise forms.ValidationError("Выбранный пакет не поддерживает загрузку видео.")

            # Проверка на наличие программы
            if not package.has_program_and_speakers and program_file:
                raise forms.ValidationError("Выбранный пакет не поддерживает загрузку программы мероприятия.")

        return cleaned_data

    class Meta:
        model = Event
        fields = [
            "title",
            "description_short",
            "description_full",
            "date_time",
            "place_data",
            "image",
            "video_url",
            "program_file",
            "category",
            "tags",
            "allow_booking_without_payment",
            "auto_close_sales_hours",
            "refund_deadline_hours",
            "duration",
            "allow_platform_requests",
            "package",
        ]
        widgets = {
            "tags": forms.CheckboxSelectMultiple,
            "date_time": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "description_short": forms.Textarea(attrs={"rows": 3}),
            "description_full": forms.Textarea(attrs={"rows": 5}),
            "image": forms.FileInput(attrs={"class": "custom-media-input", "style": "display: none;"}),
            "video_url": forms.FileInput(attrs={"class": "custom-media-input", "style": "display: none;"}),
            "program_file": forms.FileInput(attrs={"class": "custom-media-input", "style": "display: none;"}),
            "duration": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "ЧЧ:ММ",
                    "pattern": "[0-9]{2}:[0-9]{2}",
                    "title": "Формат: ЧЧ:ММ (например, 02:30)",
                }
            ),
        }


class DocumentUploadForm(forms.ModelForm):
    """
    Форма для загрузки документов партнёром.
    """

    class Meta:
        model = PartnerDocument
        fields = ["document"]
        labels = {
            "document": "Загрузите документы для верификации",
        }
        help_texts = {
            "document": "Загрузите сканы или фотографии документов, подтверждающих вашу квалификацию.",
        }
        widgets = {
            "document": forms.ClearableFileInput(attrs={"multiple": False}),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.user = self.user
        if commit:
            instance.save()
        return instance


class ReportScheduleForm(forms.ModelForm):
    """
    Форма для настройки расписания отправки отчётов.
    """

    def __init__(self, *args, **kwargs):
        self.partner = kwargs.pop("partner", None)
        super().__init__(*args, **kwargs)

        # Настройка видимости полей в зависимости от выбранных опций
        if self.instance and self.instance.frequency:
            self.setup_field_visibility()

        # Устанавливаем email партнёра по умолчанию
        if self.partner and not self.instance.email:
            self.fields["email"].initial = self.partner.email

    def setup_field_visibility(self):
        frequency = self.data.get(
            "frequency", self.instance.frequency if self.instance else None
        )
        period_type = self.data.get(
            "period_type", self.instance.period_type if self.instance else None
        )

        # Скрываем поля, которые не нужны для текущей частоты
        if frequency == "daily":
            self.fields["day_of_week"].widget = forms.HiddenInput()
            self.fields["day_of_month"].widget = forms.HiddenInput()
        elif frequency == "weekly":
            self.fields["day_of_month"].widget = forms.HiddenInput()
        elif frequency == "monthly":
            self.fields["day_of_week"].widget = forms.HiddenInput()

        # Скрываем custom_period_days если не выбран custom период
        if period_type != "custom":
            self.fields["custom_period_days"].widget = forms.HiddenInput()

    class Meta:
        model = ReportSchedule
        fields = [
            "is_active",
            "frequency",
            "report_format",
            "period_type",
            "email",
            "day_of_week",
            "day_of_month",
            "custom_period_days",
        ]
        widgets = {
            "day_of_week": forms.Select(
                choices=[
                    (0, "Понедельник"),
                    (1, "Вторник"),
                    (2, "Среда"),
                    (3, "Четверг"),
                    (4, "Пятница"),
                    (5, "Суббота"),
                    (6, "Воскресенье"),
                ]
            ),
            "day_of_month": forms.NumberInput(attrs={"min": 1, "max": 31}),
            "custom_period_days": forms.NumberInput(attrs={"min": 1}),
        }
        labels = {
            "is_active": "Активировать рассылку",
            "frequency": "Частота отправки",
            "report_format": "Формат отчёта",
            "period_type": "Период отчёта",
            "email": "Email для отправки",
            "day_of_week": "День недели",
            "day_of_month": "День месяца",
            "custom_period_days": "Количество дней для отчёта",
        }
        help_texts = {
            "day_of_week": "Выберите день недели (0 - Понедельник, 6 - Воскресенье)",
            "day_of_month": "Выберите день месяца (1-31)",
            "custom_period_days": "Укажите количество дней для произвольного периода отчёта",
        }

    def clean(self):
        cleaned_data = super().clean()
        frequency = cleaned_data.get("frequency")
        period_type = cleaned_data.get("period_type")

        print("Cleaning form data:", cleaned_data)  # Отладочный вывод

        # Проверка обязательных полей в зависимости от частоты
        if frequency == "weekly" and "day_of_week" not in cleaned_data:
            self.add_error(
                "day_of_week", "Укажите день недели для еженедельной рассылки"
            )

        if frequency == "monthly" and "day_of_month" not in cleaned_data:
            self.add_error(
                "day_of_month", "Укажите день месяца для ежемесячной рассылки"
            )

        if period_type == "custom" and not cleaned_data.get("custom_period_days"):
            self.add_error(
                "custom_period_days",
                "Укажите количество дней для произвольного периода",
            )

        print("Form errors after cleaning:", self.errors)  # Отладочный вывод
        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.partner = self.partner

        if commit:
            instance.save()
            print(
                f"Saved schedule for {instance.partner.email}: {instance.frequency}, {instance.report_format}"
            )  # Отладочный вывод
        return instance


class PayoutDetailsForm(forms.ModelForm):
    class Meta:
        model = PayoutDetails
        fields = ['bank_name', 'account_number', 'account_holder', 'inn']
        
        # Добавим более понятные подсказки (лейблы)
        labels = {
            'bank_name': 'Банк',
            'account_number': 'Номер счёта или карты',
            'account_holder': 'ФИО владельца счёта',
            'inn': 'ИНН (необязательно)',
        }