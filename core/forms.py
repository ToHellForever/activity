from django import forms
from django.forms import ModelForm
from .models import Event
from django.contrib.auth import authenticate
from django.contrib.auth.forms import UserCreationForm, PasswordChangeForm
from .models import CustomUser
from .models import SupportTicket
from partner_app.models import PartnerProfile

class EventAdminForm(ModelForm):
    class Meta:
        model = Event
        fields = '__all__'

    class Media:
        js = ('js/event_admin.js',)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        if self.instance and self.instance.place_data:
            place_data = self.instance.place_data
            if isinstance(place_data, dict):
                self.initial['latitude'] = place_data.get('latitude')
                self.initial['longitude'] = place_data.get('longitude')
                self.initial['address'] = place_data.get('address')
                self.initial['city'] = place_data.get('city')
                self.initial['district'] = place_data.get('district')
                self.initial['metro'] = place_data.get('metro')

    def save(self, commit=True):
        instance = super().save(commit=False)
        
        place_data = instance.place_data or {}
        if isinstance(place_data, str):
            import json
            try:
                place_data = json.loads(place_data)
            except json.JSONDecodeError:
                place_data = {}
        
        if self.cleaned_data.get('latitude'):
            place_data['latitude'] = float(self.cleaned_data['latitude'])
        if self.cleaned_data.get('longitude'):
            place_data['longitude'] = float(self.cleaned_data['longitude'])
        if self.cleaned_data.get('address'):
            place_data['address'] = self.cleaned_data['address']
        if self.cleaned_data.get('city'):
            place_data['city'] = self.cleaned_data['city']
        if self.cleaned_data.get('district'):
            place_data['district'] = self.cleaned_data['district']
        if self.cleaned_data.get('metro'):
            place_data['metro'] = self.cleaned_data['metro']
        
        instance.place_data = place_data
        
        if commit:
            instance.save()
        return instance
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


# --- ФОРМА РЕГИСТРАЦИИ ПАРТНЁРА ---
class PartnerRegistrationForm(forms.Form):
    """Полная форма регистрации партнёра со всеми полями профиля."""

    # Основные данные
    company_name = forms.CharField(
        max_length=255,
        required=True,
        label="Название организации / ФИО",
        widget=forms.TextInput(attrs={"placeholder": "Название организации / ФИО"}),
    )
    short_name = forms.CharField(
        max_length=255,
        required=False,
        label="Краткое наименование, бренд/торговое имя",
        widget=forms.TextInput(attrs={"placeholder": "Краткое наименование, бренд/торговое имя"}),
    )
    registration_type = forms.ChoiceField(
        choices=PartnerProfile.REGISTRATION_TYPE_CHOICES,
        required=True,
        label="Тип лица",
        initial="legal",
    )
    description = forms.CharField(
        required=False,
        max_length=500,
        label="Описание организации",
        widget=forms.Textarea(attrs={"rows": 3, "placeholder": "Описание организации. Кратко о деятельности (до 500 символов)"}),
    )

    # Реквизиты
    ogrn = forms.CharField(
        max_length=15,
        required=False,
        label="ОГРН/ОГРНИП",
        widget=forms.TextInput(attrs={"placeholder": "ОГРН/ОГРНИП"}),
    )
    inn = forms.CharField(
        max_length=20,
        required=False,
        label="ИНН",
        widget=forms.TextInput(attrs={"placeholder": "ИНН"}),
    )
    kpp = forms.CharField(
        max_length=9,
        required=False,
        label="КПП",
        widget=forms.TextInput(attrs={"placeholder": "КПП"}),
    )

    # Адреса
    legal_address = forms.CharField(
        max_length=255,
        required=False,
        label="Юридический адрес",
        widget=forms.TextInput(attrs={"placeholder": "Юридический адрес"}),
    )
    actual_address = forms.CharField(
        max_length=255,
        required=False,
        label="Фактический адрес (если отличается)",
        widget=forms.TextInput(attrs={"placeholder": "Фактический адрес (если отличается)"}),
    )

    # Контакты
    website = forms.URLField(
        required=False,
        label="Сайт компании URL",
        widget=forms.URLInput(attrs={"placeholder": "Сайт компании URL"}),
    )
    contact_person = forms.CharField(
        max_length=255,
        required=True,
        label="Контактное лицо (имя)",
        widget=forms.TextInput(attrs={"placeholder": "Контактное лицо (имя)"}),
    )
    phone = forms.CharField(
        max_length=30,
        required=True,
        label="Телефон",
        widget=forms.TextInput(attrs={"placeholder": "Телефон"}),
    )
    email = forms.EmailField(
        required=True,
        label="E-mail",
        widget=forms.EmailInput(attrs={"placeholder": "E-mail"}),
    )

    # Портфолио и ссылки
    vk_link = forms.URLField(
        required=False,
        label="VK",
        widget=forms.URLInput(attrs={"placeholder": "VK"}),
    )
    max_link = forms.URLField(
        required=False,
        label="MAX",
        widget=forms.URLInput(attrs={"placeholder": "MAX"}),
    )
    telegram_link = forms.URLField(
        required=False,
        label="Telegram",
        widget=forms.URLInput(attrs={"placeholder": "Telegram"}),
    )
    cases = forms.CharField(
        required=False,
        label="Кейсы/прошедшие мероприятия",
        widget=forms.Textarea(attrs={"rows": 3, "placeholder": "Кейсы/прошедшие мероприятия. Ссылки или краткое описание"}),
    )
    reviews = forms.CharField(
        required=False,
        label="Отзывы и публикации в СМИ",
        widget=forms.Textarea(attrs={"rows": 3, "placeholder": "Отзывы и публикации в СМИ. Ссылки"}),
    )

    # Файлы
    logo = forms.FileField(
        required=False,
        label="Логотип",
        widget=forms.FileInput(attrs={"accept": "image/png,image/svg+xml,image/jpeg"}),
    )

    # Согласия
    agree_terms = forms.BooleanField(
        required=True,
        label="Я подтверждаю достоверность указанных данных",
    )
    agree_user_agreement = forms.BooleanField(
        required=True,
        label="Согласен(на) с пользовательским соглашением и офертой",
    )
    agree_personal_data = forms.BooleanField(
        required=True,
        label="Согласен(на) на обработку персональных данных",
    )
    agree_publish_profile = forms.BooleanField(
        required=False,
        label="Разрешаю публикацию профиля организации на платформе",
    )

    # Пароли
    password1 = forms.CharField(
        required=True,
        label="Пароль",
        widget=forms.PasswordInput,
        min_length=8,
    )
    password2 = forms.CharField(
        required=True,
        label="Повторите пароль",
        widget=forms.PasswordInput,
        min_length=8,
    )

    def clean_phone(self):
        phone = self.cleaned_data.get("phone", "")
        if phone:
            digits = phone.replace("+", "").replace("-", "").replace("(", "").replace(")", "").replace(" ", "")
            if not digits.isdigit() or len(digits) < 10:
                raise forms.ValidationError("Введите корректный номер телефона")
        return phone

    def clean(self):
        cleaned_data = super().clean()
        password1 = cleaned_data.get("password1")
        password2 = cleaned_data.get("password2")
        email = cleaned_data.get("email")

        if password1 and password2 and password1 != password2:
            self.add_error("password2", "Пароли не совпадают.")

        if email and CustomUser.objects.filter(email=email).exists():
            self.add_error("email", "Пользователь с таким email уже существует.")

        return cleaned_data


# --- ФОРМА РЕДАКТИРОВАНИЯ ПРОФИЛЯ ПАРТНЕРА ---
class PartnerProfileForm(forms.ModelForm):
    """Форма для редактирования профиля партнера."""

    email = forms.EmailField(required=True)  # Делаем email обязательным

    class Meta:
        model = PartnerProfile
        # Здесь перечислены все поля, которые партнер может менять
        fields = [
            "company_name",
            "short_name",
            "description",
            "ogrn",
            "inn",
            "kpp",
            "legal_address",
            "actual_address",
            "website",
            "contact_person",
            "phone",
            "email",
            "social_links",
            "vk_link",
            "max_link",
            "telegram_link",
            "cases",
            "reviews",
            "logo",
            "video_business_card",
        ]

        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
            "social_links": forms.Textarea(
                attrs={"placeholder": "Ссылки по одной на строку"}
            ),
            "cases": forms.Textarea(attrs={"rows": 3}),
            "reviews": forms.Textarea(attrs={"rows": 3}),
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


# --- ФОРМА ДЛЯ АДМИНКИ ПАРТНЁРОВ ---
class PartnerAdminForm(forms.ModelForm):
    """Кастомная форма для админки партнёров с чекбоксами прав."""
    
    can_create_events = forms.BooleanField(
        required=False,
        label="Создавать мероприятия",
        help_text="Разрешить партнёру создавать и управлять мероприятиями"
    )
    can_request_reports = forms.BooleanField(
        required=False,
        label="Запрашивать отчёты",
        help_text="Разрешить партнёру генерировать и скачивать отчёты"
    )
    can_request_payments = forms.BooleanField(
        required=False,
        label="Запрашивать выплаты",
        help_text="Разрешить партнёру запрашивать выплаты средств"
    )
    rejection_reason = forms.CharField(
        required=False,
        label="Причина отклонения",
        widget=forms.Textarea(attrs={"rows": 3, "placeholder": "Укажите причину, по которой заявка партнёра была отклонена..."}),
        help_text="Эта причина будет показана партнёру в его кабинете"
    )
    
    class Meta:
        model = CustomUser
        fields = ['permissions', 'rejection_reason', 'verification_status', 'is_verified']
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Загружаем текущие права из JSON
        if self.instance and self.instance.permissions:
            perms = self.instance.permissions
            self.fields['can_create_events'].initial = perms.get('can_create_events', False)
            self.fields['can_request_reports'].initial = perms.get('can_request_reports', False)
            self.fields['can_request_payments'].initial = perms.get('can_request_payments', False)
    
    def clean(self):
        cleaned_data = super().clean()
        # Собираем права обратно в JSON
        permissions = {
            'can_create_events': cleaned_data.get('can_create_events', False),
            'can_request_reports': cleaned_data.get('can_request_reports', False),
            'can_request_payments': cleaned_data.get('can_request_payments', False),
        }
        cleaned_data['permissions'] = permissions
        return cleaned_data
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.permissions = self.cleaned_data['permissions']
        if commit:
            instance.save()
        return instance

    def save_m2m(self):
        # Переопределяем, чтобы не сохранять m2m поля
        pass
