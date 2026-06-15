def admin_quick_links(request):
    """
    Добавляет быстрые ссылки в контекст для админ-панели.
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
        ]
    }
