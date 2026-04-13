from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend


class EmailBackend(ModelBackend):
    """
    Аутентификация по email вместо username.
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        UserModel = get_user_model()
        try:
            # Ищем пользователя по email (возвращаем первого найденного)
            user = UserModel.objects.filter(email=username).first()
            if user and user.check_password(password):
                return user
        except UserModel.DoesNotExist:
            return None
