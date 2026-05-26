from django import forms
from django.forms import ModelForm
from .models import Event
from django.contrib.auth import authenticate
from django.contrib.auth.forms import UserCreationForm, PasswordChangeForm
from .models import CustomUser
from .models import SupportTicket

class EventAdminForm(ModelForm):
    class Meta:
        model = Event
        fields = '__all__'

    class Media:
        js = ('js/event_admin.js',)
# --- ФОРМА ВХОДА ---
class CustomAuthenticationForm(forms.Form):
    """Форма для входа с автоматической проверкой роли."""

    email = forms.EmailField(label="Email")
    password = forms.CharField(label="Пароль", widget=forms.PasswordInput)

    def __init__(self, *args, **kwargs):
        self._request = kwargs.pop("request", None)
        super().__init__(*args, **kwargs)

    def clean(self):
        """Проверяет email и пароль."""
        cleaned_data = super().clean()
        email = cleaned_data.get("email")
        password = cleaned_data.get("password")

        if email and password:
            user = authenticate(
                request=self._request, username=email, password=password
            )
            if not user:
                raise forms.ValidationError("Неверный email или пароль.")
            self.cleaned_data["user"] = user
        return cleaned_data


# --- ФОРМА РЕГИСТРАЦИИ ---
class CustomUserCreationForm(UserCreationForm):
    """Форма для регистрации с выбором роли."""

    email = forms.EmailField(label="Email", required=True)
    user_type = forms.ChoiceField(
        label="Регистрация как:",
        choices=[
            choice for choice in CustomUser.USER_TYPE_CHOICES if choice[0] != "guest"
        ],
        widget=forms.RadioSelect,
        initial="visitor",
    )

    phone_number = forms.CharField(max_length=30, required=False)
    contact_person = forms.CharField(max_length=255, required=False)

    class Meta:
        model = CustomUser
        fields = (
            "email",
            "password1",
            "password2",
            "user_type",
            "phone_number",
            "contact_person",
        )

    def clean_email(self):
        email = self.cleaned_data.get("email")
        if email:
            # Проверяем, существует ли пользователь с таким email
            if CustomUser.objects.filter(email=email).exists():
                raise forms.ValidationError(
                    "Пользователь с таким email уже существует."
                )
        return email

    def clean(self):
        cleaned_data = super().clean()
        user_type = cleaned_data.get("user_type")

        if user_type == "partner":
            phone_number = cleaned_data.get("phone_number")
            contact_person = cleaned_data.get("contact_person")

            if not phone_number:
                self.add_error("phone_number", "Это поле обязательно для партнёра.")

            if not contact_person:
                self.add_error("contact_person", "Это поле обязательно для партнёра.")

        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.username = user.email  # Используем email как username
        if commit:
            user.save()
        return user

    def send_verification_code(self, request):
        """Отправляет код подтверждения на почту пользователя."""
        import random
        from django.core.mail import EmailMultiAlternatives
        from django.conf import settings
        from django.template.loader import render_to_string

        # Генерация случайного 5-значного кода
        code = ''.join([str(random.randint(0, 9)) for _ in range(5)])

        # Сохраняем код в базе данных
        from .models import EmailVerificationCode
        EmailVerificationCode.objects.create(user=self.instance, code=code)

        # Отправляем код на почту
        subject = "Подтверждение почты"
        context = {'code': code}
        html_content = render_to_string('emails/email_verification.html', context)
        msg = EmailMultiAlternatives(subject, '', settings.DEFAULT_FROM_EMAIL, [self.instance.email])
        msg.attach_alternative(html_content, "text/html")
        msg.send()


# --- ФОРМА РЕДАКТИРОВАНИЯ ПРОФИЛЯ ПАРТНЕРА ---
class PartnerProfileForm(forms.ModelForm):
    """Форма для редактирования профиля партнера."""

    email = forms.EmailField(required=True)  # Делаем email обязательным

    class Meta:
        model = CustomUser
        # Здесь перечислены все поля, которые партнер может менять
        fields = [
            "first_name",
            "last_name",
            "email",
            "phone_number",
            "company_name",
            "logo",
            "video_business_card",
            "social_links",
        ]

        widgets = {
            # Подсказка для соцсетей
            "social_links": forms.Textarea(
                attrs={"placeholder": "Ссылки по одной на строку"}
            ),
            "video_business_card": forms.FileInput(
                attrs={
                    "accept": "video/mp4,video/quicktime,video/x-msvideo",
                    "class": "custom-media-input",
                    "style": "display: none;",
                    "help_text": "Максимальная длительность видео: 5 минут",
                }
            ),
        }


class SupportTicketForm(forms.ModelForm):
    """Форма для создания обращения в поддержку."""

    class Meta:
        model = SupportTicket
        fields = ["subject"]
        widgets = {
            "subject": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Тема обращения"}
            ),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        self.events = kwargs.pop("events", None)
        super().__init__(*args, **kwargs)

        if self.events:
            self.fields["event"] = forms.ChoiceField(
                choices=[(None, "---")]
                + [
                    (event.id, event.title)
                    for event in self.events
                    if event.has_sold_tickets
                ],
                required=False,
                widget=forms.Select(attrs={"class": "form-control"}),
                label="Связанное мероприятие",
            )
