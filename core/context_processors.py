from django.conf import settings


def admin_quick_links(request):
    """
    Добавляет быстрые ссылки и API-ключи в контекст для админ-панели.
    """
    return {
        'quick_links': [
            {
                'name': 'Дашборд модератора',
                'url': '/moderator/',
                'icon': '📋',
                'description': 'Управление обращениями в поддержке'
            },
            {
                'name': 'Реестр продаж',
                'url': '/reports/sales-register/',
                'icon': '📊',
                'description': 'Отчёт по продажам всех партнёров'
            },
        ],
        'YANDEX_MAPS_API_KEY': getattr(settings, 'YANDEX_MAPS_API_KEY', ''),
    }
