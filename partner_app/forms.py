from django import forms
from django.contrib.auth import get_user_model
from core.models import Event, PartnerDocument

User = get_user_model()


class EventForm(forms.ModelForm):
    """
    Форма для создания и редактирования мероприятия.
    """

    ticket_types = forms.CharField(
        required=False,
        label='Типы билетов (по одному на строку, формат: "Название:Цена:Количество")',
        widget=forms.Textarea(
            attrs={"placeholder": "Пример:\nVIP:1000:50\nСтандарт:500:200"}
        ),
        help_text="Укажите каждый тип билета на отдельной строке",
    )

    class Meta:
        model = Event
        fields = [
            "title",
            "description_short",
            "description_full",
            "date_time",
            "place",
            "image",
            "video_url",
            "program_file",
            "category",
            "tags",
            "allow_booking_without_payment",
            "auto_close_sales_hours",
        ]
        widgets = {
            "date_time": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "description_short": forms.Textarea(attrs={"rows": 3}),
            "description_full": forms.Textarea(attrs={"rows": 5}),
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


