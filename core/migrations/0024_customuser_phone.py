# Generated manually for adding phone field to CustomUser

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0023_ticket_color_and_image_primary'),
    ]

    operations = [
        migrations.AddField(
            model_name='customuser',
            name='phone',
            field=models.CharField(blank=True, max_length=30, null=True, verbose_name='Телефон'),
        ),
    ]
