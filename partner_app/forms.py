from core.models import Event, Ticket
from django import forms

class EventForm(forms.ModelForm):
    """Форма для создания и редактирования мероприятия."""
    
    # Поле для загрузки видео с компьютера
    video_url = forms.FileField(required=False, label="Видео (загрузить файл)")
    
    # Поле для типов билетов (как и было)
    ticket = forms.CharField(
        widget=forms.Textarea,
        label="Типы билетов (Название:Цена:Количество), каждый с новой строки",
        help_text="Пример:\nVIP:5000:20\nСтандарт:3000:50",
        required=True
    )

    class Meta:
        model = Event
        fields = [
            'title', 
            'description_short', 
            'description_full', 
            'date_time', 
            'place',
            'category',
            'image',
            'video_url',
            'program_file',
            'allow_booking_without_payment',
            'auto_close_sales_hours',
        ]
        
    def clean_ticket(self):
        """Проверяем, что данные о билетах введены корректно."""
        data = self.cleaned_data['ticket']
        if not data.strip():
            raise forms.ValidationError("Необходимо указать хотя бы один тип билетов.")
        return data