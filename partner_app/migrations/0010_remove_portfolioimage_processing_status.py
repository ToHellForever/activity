# Manual migration to remove processing_status column from portfolioimage

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('partner_app', '0009_alter_portfolioitem_description'),
    ]

    operations = [
        migrations.RunSQL(
            sql="ALTER TABLE partner_app_portfolioimage DROP COLUMN processing_status;",
            reverse_sql="ALTER TABLE partner_app_portfolioimage ADD COLUMN processing_status VARCHAR(20) NOT NULL DEFAULT 'pending';",
        ),
    ]
