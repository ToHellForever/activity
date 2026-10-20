from django.db import migrations, models
import django.db.models.deletion


def seed_current_consent_state(apps, schema_editor):
    CustomUser = apps.get_model("core", "CustomUser")
    MarketingConsentEvent = apps.get_model("core", "MarketingConsentEvent")
    database = schema_editor.connection.alias

    existing_user_ids = set(
        MarketingConsentEvent.objects.using(database)
        .filter(user__isnull=False)
        .values_list("user_id", flat=True)
    )
    history = [
        MarketingConsentEvent(
            user_id=user.pk,
            email=user.email,
            consent=user.consent_marketing,
            changed_at=user.consent_marketing_at,
        )
        for user in CustomUser.objects.using(database)
        .filter(consent_marketing_at__isnull=False)
        .iterator()
        if user.pk not in existing_user_ids
    ]
    MarketingConsentEvent.objects.using(database).bulk_create(history)


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0051_seed_partner_agreement_and_faq"),
    ]

    operations = [
        migrations.DeleteModel(
            name="MarketingConsentUser",
        ),
        migrations.CreateModel(
            name="MarketingConsentEvent",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("email", models.EmailField(max_length=254, verbose_name="Почта")),
                ("consent", models.BooleanField(verbose_name="Статус согласия")),
                ("changed_at", models.DateTimeField(verbose_name="Дата изменения")),
                (
                    "user",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="marketing_consent_events",
                        to="core.customuser",
                        verbose_name="Пользователь",
                    ),
                ),
            ],
            options={
                "verbose_name": "История согласия на рассылку",
                "verbose_name_plural": "История согласий на рассылку",
                "ordering": ("-changed_at", "-pk"),
            },
        ),
        migrations.RunPython(seed_current_consent_state, migrations.RunPython.noop),
    ]
