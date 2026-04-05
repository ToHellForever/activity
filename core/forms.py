# core/forms.py

from django import forms
from django.contrib.auth import authenticate
from django.contrib.auth.forms import UserCreationForm, PasswordChangeForm
from .models import CustomUser

# --- ФОРМА ВХОДА ---
class CustomAuthenticationForm(forms.Form):
    """Форма для входа с автоматической проверкой роли."""
    username = forms.CharField(label='Логин')
    password = forms.CharField(label='Пароль', widget=forms.PasswordInput)

    def clean(self):
        """Проверяет только логин и пароль."""
        cleaned_data = super().clean()
        username = cleaned_data.get('username')
        password = cleaned_data.get('password')

        if username and password:
            user = authenticate(username=username, password=password)
            if not user:
                raise forms.ValidationError("Неверный логин или пароль.")
            self.cleaned_data['user'] = user
        return cleaned_data

# --- ФОРМА РЕГИСТРАЦИИ ---
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
        fields = ('username', 'user_type')

# --- ФОРМА РЕДАКТИРОВАНИЯ ПРОФИЛЯ ПАРТНЕРА ---
class PartnerProfileForm(forms.ModelForm):
    """Форма для редактирования профиля партнера."""
    email = forms.EmailField(required=True) # Делаем email обязательным

    class Meta:
        model = CustomUser
        # Здесь перечислены все поля, которые партнер может менять
        fields = ['first_name', 'last_name', 'email', 'phone_number', 'company_name', 'logo', 'social_links']
        
        widgets = {
            # Подсказка для соцсетей
            'social_links': forms.Textarea(attrs={'placeholder': 'Ссылки по одной на строку'}),
        }