from core.models import Event, Ticket
from django import forms

class EventForm(forms.ModelForm):
    """Форма для создания и редактирования мероприятия."""
    
    # Создаем поле для типов билетов. Мы будем добавлять их динамически.
    # Это поле не связано напрямую с моделью Event, оно нужно для формы.
    ticket = forms.CharField(
        widget=forms.Textarea,
        label="Типы билетов (Название:Цена:Количество), каждый с новой строки",
        help_text="Пример:\nVIP:5000:20\nСтандарт:3000:50",
        required=True
    )

    class Meta:
        model = Event
        # Поля, которые партнер будет заполнять в форме
        fields = [
            'title', 
            'description_short', 
            'description_full', 
            'date_time', 
            'place', 
            'image',
            'auto_close_sales_hours'
        ]
        
    def clean_ticket(self):
        """Проверяем, что данные о билетах введены корректно."""
        data = self.cleaned_data['ticket']
        if not data.strip():
            raise forms.ValidationError("Необходимо указать хотя бы один тип билетов.")
        return data