from django import forms
from django.contrib.auth import authenticate

class CustomAuthenticationForm(forms.Form):
    username = forms.CharField(label='Логин')
    password = forms.CharField(label='Пароль', widget=forms.PasswordInput)
    user_type = forms.ChoiceField(
        label='Войти как',
        choices=[('visitor', 'Посетитель'), ('partner', 'Партнёр')],
        widget=forms.RadioSelect,
        initial='visitor'
    )

    def clean(self):
        cleaned_data = super().clean()
        username = cleaned_data.get('username')
        password = cleaned_data.get('password')
        user_type = cleaned_data.get('user_type')

        if username and password:
            # Аутентифицируем пользователя (проверяем логин и пароль)
            user = authenticate(username=username, password=password)
            
            if not user:
                raise forms.ValidationError("Неверный логин или пароль.")
                
            # Проверяем, совпадает ли тип пользователя с выбранным в форме
            if user.user_type != user_type:
                raise forms.ValidationError(
                    f"Вы выбрали '{user_type}', но этот пользователь является '{user.user_type}'."
                )
                
            self.cleaned_data['user'] = user
        return cleaned_data