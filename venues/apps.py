from django.apps import AppConfig


class VenuesConfig(AppConfig):
    name = 'venues'
    
    def ready(self):
        import venues.signals
