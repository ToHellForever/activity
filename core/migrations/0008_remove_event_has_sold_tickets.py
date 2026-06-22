# Generated migration to remove has_sold_tickets column from Event model

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0007_remove_ticket_price_description_and_more'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='event',
            name='has_sold_tickets',
        ),
    ]
