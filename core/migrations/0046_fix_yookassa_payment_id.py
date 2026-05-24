from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ('core', '0045_fix_yookassa_payment_id'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                # Никаких изменений в базе данных не требуется, так как столбец уже существует
            ],
            state_operations=[
                # Указываем Django, что поле уже существует
                migrations.AddField(
                    model_name='order',
                    name='yookassa_payment_id',
                    field=models.CharField(blank=True, max_length=255, null=True, verbose_name='Идентификатор платежа в ЮКассе'),
                ),
            ]
        ),
    ]