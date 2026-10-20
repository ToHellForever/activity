from pathlib import Path, PurePosixPath

import core.models
import core.storage_backends
from django.conf import settings
from django.core.files import File
from django.core.files.storage import default_storage
from django.core.validators import FileExtensionValidator
from django.db import migrations, models


def migrate_faq_icons(apps, schema_editor):
    FAQCategory = apps.get_model("core", "FAQCategory")
    if settings.USE_YANDEX_CLOUD:
        storage = core.storage_backends.YandexCloudWithProcessingStorage()
    else:
        storage = default_storage
    database = schema_editor.connection.alias

    for category in FAQCategory.objects.using(database).exclude(icon="").iterator():
        legacy_path = category.icon.name.replace("\\", "/").lstrip("/")
        if legacy_path.startswith("media/"):
            legacy_path = legacy_path[len("media/"):]
        relative_path = PurePosixPath(legacy_path)
        if ".." in relative_path.parts:
            category.icon = ""
            category.save(update_fields=["icon"])
            continue

        source_path = Path(settings.MEDIA_ROOT) / Path(*relative_path.parts)
        if not source_path.is_file():
            source_path = Path(settings.BASE_DIR) / "media" / Path(*relative_path.parts)
        if not source_path.is_file():
            category.icon = ""
            category.save(update_fields=["icon"])
            continue

        target_name = f"faq/icons/{source_path.name}"
        if not storage.exists(target_name):
            with source_path.open("rb") as source_file:
                target_name = storage.save(target_name, File(source_file))
        category.icon = target_name
        category.save(update_fields=["icon"])


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0052_marketingconsentevent"),
    ]

    operations = [
        migrations.AlterField(
            model_name="faqcategory",
            name="icon",
            field=models.FileField(
                blank=True,
                help_text="Загрузите SVG, PNG, JPG или WebP, не более 2 МБ.",
                storage=core.storage_backends.YandexCloudWithProcessingStorage(),
                upload_to="faq/icons/",
                validators=[
                    FileExtensionValidator(
                        allowed_extensions=("svg", "png", "jpg", "jpeg", "webp")
                    ),
                    core.models.validate_faq_icon_size,
                ],
                verbose_name="Иконка",
            ),
        ),
        migrations.RunPython(migrate_faq_icons, migrations.RunPython.noop),
    ]
