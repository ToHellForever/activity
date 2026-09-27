"""Заполняет номера агентских договоров существующим партнёрам (с 1, по дате создания профиля)."""
from django.db import migrations


def assign_numbers(apps, schema_editor):
    PartnerProfile = apps.get_model("partner_app", "PartnerProfile")
    number = 0
    # По порядку создания профилей — id растёт с датой регистрации
    for profile in PartnerProfile.objects.order_by("id"):
        number += 1
        PartnerProfile.objects.filter(pk=profile.pk).update(
            agent_contract_number=number
        )


def remove_numbers(apps, schema_editor):
    PartnerProfile = apps.get_model("partner_app", "PartnerProfile")
    PartnerProfile.objects.update(agent_contract_number=None)


class Migration(migrations.Migration):

    dependencies = [
        ("partner_app", "0018_partnerprofile_agent_contract_number_and_more"),
    ]

    operations = [
        migrations.RunPython(assign_numbers, remove_numbers),
    ]
