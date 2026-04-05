from django import forms
from django.contrib.auth import authenticate
from django.contrib.auth.forms import UserCreationForm
from .models import CustomUser
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
        
        
        