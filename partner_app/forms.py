from django import forms
from django.contrib.auth import get_user_model
from core.models import Event, PartnerDocument

User = get_user_model()


class EventForm(forms.ModelForm):
    """
    Форма для создания и редактирования мероприятия.
    """

    video_changed = forms.BooleanField(
        widget=forms.HiddenInput(), required=False, initial=False
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Делаем поля обязательными
        self.fields["title"].required = True
        self.fields["description_short"].required = True
        self.fields["description_full"].required = True
        self.fields["date_time"].required = True
        self.fields["place"].required = True
        self.fields["image"].required = True
        self.fields["refund_deadline_hours"].required = True

        # Кастомные сообщения об ошибках
        self.fields["date_time"].error_messages = {
            "required": "Пожалуйста, укажите дату и время проведения мероприятия."
        }

        # Добавляем обработчик для поля video_url
        if "video_url" in self.fields:
            self.fields["video_url"].widget.attrs.update(
                {
                    "onchange": 'document.getElementById("id_video_changed").value = "True"'
                }
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
            "refund_deadline_hours",
        ]
        widgets = {
            "date_time": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "description_short": forms.Textarea(attrs={"rows": 3}),
            "description_full": forms.Textarea(attrs={"rows": 5}),
        }
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
