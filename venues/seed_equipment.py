"""
Скрипт для загрузки категорий оборудования и подкатегорий.
Запуск: python manage.py shell < venues/seed_equipment.py
"""

from venues.models import EquipmentCategory, EquipmentItem

# Данные: категория -> список элементов оборудования
EQUIPMENT_DATA = {
    "Базовое презентационное оборудование": [
        "Проектор",
        "Экран",
        "Флипчарт",
        "Магнитно-маркерная доска",
        "Лазерная указка",
        "Кликер для презентаций",
    ],
    "Звук и речь": [
        "Акустическая система",
        "Колонки",
        "Микрофон ручной",
        "Петличный микрофон",
    ],
    "Для работы участников": [
        "Стол",
        "Стул",
        "Трибуна для спикера",
        "Рабочее место тренера",
        "Розетки у мест участников",
        "Блокноты и канцелярия",
        "Кулер с водой",
    ],
    "Для комфорта и организации": [
        "Кондиционер",
        "Регулируемое освещение",
        "Гардероб",
        "Зона регистрации",
        "Навигация внутри площадки",
        "Кофе-брейк зона",
        "Отдельная зона для общения",
        "Туалеты рядом с залом",
        "Парковка",
    ],
    "Техническое подключение": [
        "Wi-Fi",
        "HDMI",
        "Type-C",
        "VGA",
        "Ноутбук по запросу",
        "Технический специалист на площадке",
    ],
}


def seed_equipment():
    created_categories = []
    updated_categories = []

    for category_name, items in EQUIPMENT_DATA.items():
        # Создаём или получаем категорию
        category, created = EquipmentCategory.objects.get_or_create(
            name=category_name,
            defaults={"name": category_name}
        )
        if created:
            created_categories.append(category_name)
        else:
            updated_categories.append(category_name)

        # Добавляем элементы оборудования
        for item_name in items:
            EquipmentItem.objects.get_or_create(
                category=category,
                name=item_name,
            )

    print(f"\nСоздано категорий: {len(created_categories)}")
    for name in created_categories:
        print(f"  + {name}")

    print(f"\nОбновлено категорий: {len(updated_categories)}")
    for name in updated_categories:
        print(f"  ~ {name}")

    # Итоговая статистика
    total_categories = EquipmentCategory.objects.count()
    total_items = EquipmentItem.objects.count()
    print(f"\nИтого в базе:")
    print(f"  Категорий: {total_categories}")
    print(f"  Элементов оборудования: {total_items}")

    # Вывод деталей по каждой категории
    print("\nДетализация:")
    for cat in EquipmentCategory.objects.prefetch_related('items').all():
        items_count = cat.items.count()
        items_list = ", ".join(cat.items.values_list('name', flat=True))
        print(f"\n  {cat.name}:")
        print(f"    Элементы ({items_count}): {items_list}")


if __name__ == "__main__":
    seed_equipment()
