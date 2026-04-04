# core/forms.py

from django import forms
from django.contrib.auth import authenticate
from django.contrib.auth.forms import UserCreationForm
from .models import CustomUser

class CustomAuthenticationForm(forms.Form):
    """Форма для авторизации с выбором роли."""
    username = forms.CharField(label='Логин')
    password = forms.CharField(label='Пароль', widget=forms.PasswordInput)
    user_type = forms.ChoiceField(
        label='Войти как:',
        choices=CustomUser.USER_TYPE_CHOICES,
        widget=forms.RadioSelect,
        initial='visitor'
    )

    def clean(self):
        """Метод для проверки логина и пароля."""
        cleaned_data = super().clean()
        username = cleaned_data.get('username')
        password = cleaned_data.get('password')
        user_type = cleaned_data.get('user_type')

        if username and password:
            # Проверяем, существует ли такой пользователь
            user = authenticate(username=username, password=password)
            if not user:
                # Если пользователя нет, вызываем ошибку
                raise forms.ValidationError("Неверный логин или пароль.")
            
            # Проверяем, совпадает ли тип пользователя с выбранным в форме
            if user.user_type != user_type:
                raise forms.ValidationError(
                    f"Вы выбрали '{user_type}', но этот пользователь является '{user.user_type}'."
                )
            # Сохраняем найденного пользователя в cleaned_data
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