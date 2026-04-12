from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from django.conf import settings

User = get_user_model()


@receiver(post_save, sender=User)
def set_default_user_type(sender, instance, created, **kwargs):
    """
    После создания пользователя автоматически назначаем тип:
    - Если пользователь admin (is_staff=True), устанавливаем тип 'guest'.
    - Если пользователь не admin, устанавливаем тип 'visitor'.
    """
    if created:
        if instance.is_staff:
            # Админы изначально будут с типом "Гость"
            if instance.user_type not in ["visitor", "partner"]:
                instance.user_type = "visitor"
                instance.save()
        else:
            # Обычные пользователи получают тип "Посетитель"
            if instance.user_type == "visitor":
                instance.user_type = "guest"
                instance.save()
