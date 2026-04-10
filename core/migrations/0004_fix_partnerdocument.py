from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0003_customuser_is_verified_alter_category_id_and_more'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                # Не выполняем никаких операций с базой данных
            ],
            state_operations=[
                migrations.CreateModel(
                    name='PartnerDocument',
                    fields=[
                        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                        ('document', models.FileField(upload_to='partner_documents/', verbose_name='Документ')),
                        ('uploaded_at', models.DateTimeField(auto_now_add=True, verbose_name='Дата загрузки')),
                        ('is_approved', models.BooleanField(default=False, verbose_name='Подтверждено модератором')),
                        ('reviewed_at', models.DateTimeField(blank=True, null=True, verbose_name='Дата проверки')),
                        ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='core.customuser', verbose_name='Партнёр')),
                        ('reviewer', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='reviewed_documents', to='core.customuser', verbose_name='Модератор')),
                    ],
                    options={
                        'verbose_name': 'Документ партнёра',
                        'verbose_name_plural': 'Документы партнёров',
                    },
                ),
            ]
        ),
    ]
