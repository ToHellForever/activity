"""Доступ к юридическим текстам, редактируемым через админку.

Тексты живут в модели core.models.LegalDocument. Если записи в базе еще нет
(например, миграция с заполнением еще не применена), берется дефолтный файл
из core/legal_documents_defaults/ — страница никогда не останется пустой.
"""
from pathlib import Path
 
from django.conf import settings

DEFAULTS_DIR = Path(settings.BASE_DIR) / "core" / "legal_documents_defaults"

# slug -> (имя дефолтного файла, заголовок для админки)
LEGAL_PAGES = {
    'privacy-policy': ('privacy-policy.html', 'Политика обработки персональных данных'),
    'personal-data-consent': ('personal-data-consent.html', 'Согласие на обработку персональных данных'),
    'mailing-consent': ('mailing-consent.html', 'Согласие на рассылку'),
    'offer-participant': ('offer-participant.html', 'Оферта для пользователей сервиса'),
    'offer-organizer': ('offer-organizer.html', 'Оферта для организаторов мероприятий'),
    'offer-venue': ('offer-venue.html', 'Оферта для собственников площадок'),
}


def default_content(slug):
    """Текст по умолчанию из файла core/legal_documents_defaults/<slug>.html."""
    filename = LEGAL_PAGES.get(slug, (f"{slug}.html",))[0]
    path = DEFAULTS_DIR / filename
    if path.is_file():
        return path.read_text(encoding="utf-8")
    return ''


def get_content(slug):
    """Актуальный текст страницы: из базы, иначе дефолт из файла."""
    from core.models import LegalDocument

    content = (
        LegalDocument.objects
        .filter(slug=slug)
        .values_list('content', flat=True)
        .first()
    )
    if content and content.strip():
        return content
    return default_content(slug)


def sync_from_defaults():
    """Создает отсутствующие записи из дефолтных файлов. Идемпотентно."""
    from core.models import LegalDocument

    created = []
    for slug, (_filename, title) in LEGAL_PAGES.items():
        obj, was_created = LegalDocument.objects.get_or_create(
            slug=slug,
            defaults={'title': title, 'content': default_content(slug)},
        )
        if was_created:
            created.append(slug)
    return created
