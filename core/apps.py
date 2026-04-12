from django.apps import AppConfig


class CoreConfig(AppConfig):
    name = "core"

    def ready(self):
        # Импортируем сигналы, чтобы они зарегистрировались
        import core.signals
