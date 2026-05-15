from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ('core', '0030_order_purchase_type_alter_order_payment_status'),
    ]

    operations = [
        migrations.CreateModel(
            name='Tag',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=50, unique=True, verbose_name='Название тега')),
            ],
            options={
                'verbose_name': 'Тег',
                'verbose_name_plural': 'Теги',
                'ordering': ['name'],
            },
        ),
        migrations.RunSQL(
            """
            INSERT INTO core_tag (name) VALUES
            ('Конференция'),
            ('Мастер-класс'),
            ('Тренинг'),
            ('Вебинар'),
            ('Концерт'),
            ('Выставка'),
            ('Спорт'),
            ('Бизнес'),
            ('Образование'),
            ('Развлечение');
            """
        ),
    ]