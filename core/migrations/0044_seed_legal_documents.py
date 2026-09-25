"""Заполняет LegalDocument текстами из core/legal_documents_defaults/."""
from django.db import migrations


SLUG_TITLES = [
    ('privacy-policy', 'Политика обработки персональных данных'),
    ('personal-data-consent', 'Согласие на обработку персональных данных'),
    ('mailing-consent', 'Согласие на рассылку'),
    ('offer-participant', 'Оферта для пользователей сервиса'),
    ('offer-organizer', 'Оферта для организаторов мероприятий'),
    ('offer-venue', 'Оферта для собственников площадок'),
]


def seed_legal_documents(apps, schema_editor):
    LegalDocument = apps.get_model('core', 'LegalDocument')
    from core import legal_pages

    for slug, title in SLUG_TITLES:
        obj, created = LegalDocument.objects.get_or_create(
            slug=slug,
            defaults={
                'title': title,
                'content': legal_pages.default_content(slug),
            },
        )
        if not created and not obj.content.strip():
            obj.content = legal_pages.default_content(slug)
            obj.save(update_fields=['content'])


def unseed_legal_documents(apps, schema_editor):
    LegalDocument = apps.get_model('core', 'LegalDocument')
    LegalDocument.objects.filter(slug__in=[slug for slug, _ in SLUG_TITLES]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0043_legaldocument'),
    ]

    operations = [
        migrations.RunPython(seed_legal_documents, unseed_legal_documents),
    ]
