"""Убирает осиротевшую таблицу core_userconsent.

Миграция 0040_userconsent создавала модель UserConsent, но от этой схемы
отказались в пользу булевых полей на CustomUser
(0041_customuser_consent_marketing_and_more). Модель и файл той миграции из
кода удалены, а таблица в БД осталась.

Именно она ломает удаление пользователя в админке
(/admin/core/customuser/<id>/delete/): в таблице висит внешний ключ
user_id -> core_customuser.id с ON DELETE NO ACTION, а Django про такую
связь уже ничего не знает — коллектор удаления не включает core_userconsent
в каскад, и Postgres отвечает IntegrityError («Key (id)=(62) is still
referenced from table "core_userconsent"»).

Перед удалением таблицы переносим согласия в новые поля CustomUser, чтобы не
потерять отметки 152-ФЗ.
"""

from django.db import migrations

# consent_type из старой таблицы -> (флаг, дата) на CustomUser
CONSENT_FIELDS = {
    "personal_data": ("consent_personal_data", "consent_personal_data_at"),
    "mailing": ("consent_marketing", "consent_marketing_at"),
}

TABLE = "core_userconsent"

RECREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS "core_userconsent" (
    "id" bigserial NOT NULL PRIMARY KEY,
    "consent_type" varchar(50) NOT NULL,
    "document_version" varchar(50) NOT NULL,
    "is_active" boolean NOT NULL,
    "accepted_at" timestamp with time zone NOT NULL,
    "revoked_at" timestamp with time zone NULL,
    "ip_address" inet NULL,
    "user_agent" text NOT NULL,
    "user_id" bigint NOT NULL
)
"""


def _table_exists(schema_editor):
    return TABLE in schema_editor.connection.introspection.table_names()


def backfill_user_consents(apps, schema_editor):
    """Переносит отметки согласий из core_userconsent в CustomUser."""
    if not _table_exists(schema_editor):
        return

    CustomUser = apps.get_model("core", "CustomUser")

    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            'SELECT "user_id", "consent_type", "is_active", "accepted_at" '
            'FROM "core_userconsent" ORDER BY "accepted_at"'
        )
        rows = cursor.fetchall()

    # Считаем последней запись по каждому типу согласия (самая свежая дата)
    latest = {}
    for user_id, consent_type, is_active, accepted_at in rows:
        if consent_type in CONSENT_FIELDS:
            latest[(user_id, consent_type)] = (bool(is_active), accepted_at)

    by_user = {}
    for (user_id, consent_type), value in latest.items():
        by_user.setdefault(user_id, {})[consent_type] = value

    for user_id, consents in by_user.items():
        user = CustomUser.objects.filter(pk=user_id).first()
        if user is None:
            continue
        update_fields = []
        for consent_type, (granted, accepted_at) in consents.items():
            flag_field, date_field = CONSENT_FIELDS[consent_type]
            # Не перетираем согласия, которые пользователь уже подтвердил заново
            if getattr(user, flag_field) or getattr(user, date_field):
                continue
            setattr(user, flag_field, granted)
            setattr(user, date_field, accepted_at)
            update_fields += [flag_field, date_field]
        if update_fields:
            user.save(update_fields=update_fields)


def drop_userconsent_table(apps, schema_editor):
    if _table_exists(schema_editor):
        schema_editor.execute('DROP TABLE "core_userconsent"')


def recreate_userconsent_table(apps, schema_editor):
    """Восстанавливает только структуру таблицы (строки согласий не вернуть)."""
    if not _table_exists(schema_editor):
        schema_editor.execute(RECREATE_TABLE_SQL)


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0041_customuser_consent_marketing_and_more"),
    ]

    operations = [
        migrations.RunPython(
            backfill_user_consents,
            reverse_code=migrations.RunPython.noop,
        ),
        migrations.RunPython(
            drop_userconsent_table,
            reverse_code=recreate_userconsent_table,
        ),
    ]
