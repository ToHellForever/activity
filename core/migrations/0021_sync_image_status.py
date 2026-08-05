from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0020_delete_eventrequestproxy'),  # Укажите здесь имя файла, который шел перед удаленным 0021
    ]

    operations = [
        migrations.AddField(
            model_name='event',
            name='image_processing_status',
            field=models.CharField(
                choices=[
                    ('pending', 'Ожидает обработки'),
                    ('processing', 'Обрабатывается'),
                    ('completed', 'Обработка завершена'),
                    ('failed', 'Ошибка обработки'),
                ],
                default='pending',
                max_length=20,
                verbose_name='Статус обработки изображения',
            ),
        ),
    ]