from django.db import migrations, models
from django.core.validators import FileExtensionValidator
from core.validators import validate_and_compress_video


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="customuser",
            name="video_business_card",
            field=models.FileField(
                blank=True,
                null=True,
                upload_to="partner_video/",
                verbose_name="Видео (загрузить)",
                validators=[
                    FileExtensionValidator(allowed_extensions=["mp4", "mov", "avi"]),
                    validate_and_compress_video,
                ],
            ),
        ),
    ]
