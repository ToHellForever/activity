from django.core.management.base import BaseCommand
from venues.models import EquipmentCategory, EquipmentItem


class Command(BaseCommand):
    help = 'Загрузка категорий оборудования и элементов'

    def handle(self, *args, **options):
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

        created_categories = []
        updated_categories = []

        for category_name, items in EQUIPMENT_DATA.items():
            category, created = EquipmentCategory.objects.get_or_create(
                name=category_name,
                defaults={"name": category_name}
            )
            if created:
                created_categories.append(category_name)
            else:
                updated_categories.append(category_name)

            for item_name in items:
                EquipmentItem.objects.get_or_create(
                    category=category,
                    name=item_name,
                )

        self.stdout.write(self.style.SUCCESS(f'\nСоздано категорий: {len(created_categories)}'))
        for name in created_categories:
            self.stdout.write(f'  + {name}')

        self.stdout.write(self.style.SUCCESS(f'\nОбновлено категорий: {len(updated_categories)}'))
        for name in updated_categories:
            self.stdout.write(f'  ~ {name}')

        total_categories = EquipmentCategory.objects.count()
        total_items = EquipmentItem.objects.count()
        self.stdout.write(f'\nИтого в базе:')
        self.stdout.write(f'  Категорий: {total_categories}')
        self.stdout.write(f'  Элементов оборудования: {total_items}')

        self.stdout.write('\nДетализация:')
        for cat in EquipmentCategory.objects.prefetch_related('items').all():
            items_count = cat.items.count()
            items_list = ", ".join(cat.items.values_list('name', flat=True))
            self.stdout.write(f'\n  {cat.name}:')
            self.stdout.write(f'    Элементы ({items_count}): {items_list}')
