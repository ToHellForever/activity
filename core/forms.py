from django import forms
from django.contrib.auth import authenticate
from django.contrib.auth.forms import UserCreationForm
from .models import CustomUser
from .models import Event, Ticket
from django import forms
from django.contrib.auth import authenticate

class CustomAuthenticationForm(forms.Form):
    """Форма для входа с автоматической проверкой роли."""
    username = forms.CharField(label='Логин')
    password = forms.CharField(label='Пароль', widget=forms.PasswordInput)

    def clean(self):
        """
        Проверяет только логин и пароль.
        Роль пользователя будет проверена позже в views.py.
        """
        cleaned_data = super().clean()
        username = cleaned_data.get('username')
        password = cleaned_data.get('password')

        if username and password:
            # Проверяем, существует ли пользователь с такими данными
            user = authenticate(username=username, password=password)
            if not user:
                # Если пользователя нет, вызываем общую ошибку формы
                raise forms.ValidationError("Неверный логин или пароль.")
            
            # Сохраняем найденного пользователя в cleaned_data,
            # чтобы потом использовать его в views.py
            self.cleaned_data['user'] = user
            
        return cleaned_data

class CustomUserCreationForm(UserCreationForm):
    """Форма для регистрации с выбором роли."""
    user_type = forms.ChoiceField(
        label='Регистрация как:',
        choices=CustomUser.USER_TYPE_CHOICES,
        widget=forms.RadioSelect,
        initial='visitor'
    )

    class Meta:
        model = CustomUser
        # Поля, которые будут в форме
        fields = ('username', 'user_type')
        
        
        

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