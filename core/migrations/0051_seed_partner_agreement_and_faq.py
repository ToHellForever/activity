import os
from pathlib import Path

import core.document_storage
import core.models
from django.conf import settings
from django.core.files import File
from django.core.files.storage import default_storage
from django.core.validators import FileExtensionValidator
from django.db import migrations, models


FAQ_CONTENT = (
    (
        "Вопросы для участников",
        "/media/icon/solar_ticket-bold.svg",
        (
            (
                "Как купить билет?",
                "Выберите интересующее мероприятие, ознакомьтесь с описанием и нажмите кнопку «Купить билет». Далее следуйте инструкциям на странице оформления заказа.",
            ),
            (
                "Нужно ли регистрироваться на платформе для покупки билета?",
                "Регистрация не обязательна для покупки билета. Вы можете оформить покупку, указав только email и имя. Однако регистрация даёт доступ к личному кабинету и истории заказов.",
            ),
            (
                "Где найти купленный билет?",
                "После покупки билет придёт на указанную электронную почту. Также вы можете найти его в личном кабинете в разделе «Мои билеты».",
            ),
        ),
    ),
    (
        "Вопросы для организаторов",
        "/media/icon/ix_work-case-filled.svg",
        (
            (
                "Кто может размещать мероприятия на БизнесАфише?",
                "Размещать мероприятия могут юридические лица, индивидуальные предприниматели, специалисты, образовательные организации, бизнес-сообщества и другие организаторы, проводящие реальные офлайн-мероприятия деловой тематики.",
            ),
            (
                "Как зарегистрировать организацию?",
                "Зарегистрируйтесь на платформе, выберите роль «Организатор», заполните профиль организации и отправьте документы для верификации.",
            ),
            (
                "Какие данные организации нужно указать?",
                "Укажите наименование организации, ИНН, контактное лицо, телефон, email и реквизиты для расчётов. Все данные проверяются перед модерацией.",
            ),
            (
                "Как получить отметку «Надёжный организатор»?",
                "Отметка «Надёжный организатор» присваивается за высокую оценку мероприятий участниками, быструю реакцию на вопросы и соблюдение всех условий платформы.",
            ),
            (
                "Сколько длится проверка документов?",
                "Проверка документов занимает от 1 до 3 рабочих дней. После успешной проверки вы получите уведомление на email.",
            ),
            (
                "Какие мероприятия нельзя размещать?",
                "На платформе запрещено размещать мероприятия, связанные с незаконной деятельностью, наркотическими веществами, оружием, а также мероприятия, нарушающие законодательство РФ.",
            ),
        ),
    ),
    (
        "Общие вопросы",
        "/media/icon/_.svg",
        (
            (
                "Что такое БизнесАфиша?",
                "БизнесАфиша — это платформа деловой жизни города, где собраны офлайн-мероприятия, организаторы и площадки деловой тематики. Здесь можно найти конференции, семинары, тренинги, мастер-классы, бизнес-завтраки, презентации и другие полезные события.",
            ),
            (
                "Какие мероприятия размещаются на платформе?",
                "На платформе размещаются деловые мероприятия: конференции, семинары, мастер-классы, бизнес-завтраки, презентации, тренинги, выставки и другие события деловой направленности.",
            ),
            (
                "Можно ли разместить онлайн-мероприятие?",
                "На данный момент платформа фокусируется на офлайн-мероприятиях. Возможность размещения онлайн-мероприятий будет добавлена в будущем.",
            ),
            (
                "Как найти подходящее мероприятие?",
                "Используйте каталог мероприятий с фильтрами по дате, категории, городу и ключевым словам. Также вы можете подписаться на уведомления от интересующих вас организаторов.",
            ),
        ),
    ),
)


def seed_partner_content(apps, schema_editor):
    FAQCategory = apps.get_model("core", "FAQCategory")
    FAQItem = apps.get_model("core", "FAQItem")
    PartnerAgreement = apps.get_model("core", "PartnerAgreement")
    database = schema_editor.connection.alias

    for category_order, (name, icon, questions) in enumerate(FAQ_CONTENT):
        category, _ = FAQCategory.objects.using(database).get_or_create(
            name=name,
            defaults={"icon": icon, "order": category_order},
        )
        for item_order, (question, answer) in enumerate(questions):
            FAQItem.objects.using(database).get_or_create(
                category=category,
                question=question,
                defaults={"answer": answer, "order": item_order, "is_active": True},
            )

    if PartnerAgreement.objects.using(database).exists():
        return

    source_path = Path(settings.BASE_DIR) / "ДОГОВОР для организаторов.docx"
    if not source_path.is_file():
        raise FileNotFoundError(
            f"Не найден исходный договор для переноса: {source_path}"
        )

    stored_name = f"partner_agreements/{os.path.basename(source_path)}"
    if settings.USE_YANDEX_CLOUD:
        storage = core.document_storage.YandexDocumentProcessingStorage()
    else:
        storage = default_storage

    if not storage.exists(stored_name):
        with source_path.open("rb") as source_file:
            stored_name = storage.save(stored_name, File(source_file))

    PartnerAgreement.objects.using(database).create(file=stored_name, is_active=True)


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0050_faqcategory_partneragreement_faqitem"),
    ]

    operations = [
        migrations.CreateModel(
            name="MarketingConsentUser",
            fields=[],
            options={
                "verbose_name": "Согласие на рассылку",
                "verbose_name_plural": "Согласия на рассылку",
                "proxy": True,
                "indexes": [],
                "constraints": [],
            },
            bases=("core.customuser",),
        ),
        migrations.AlterField(
            model_name="partneragreement",
            name="file",
            field=models.FileField(
                help_text="DOCX или PDF, не более 10 МБ",
                storage=core.document_storage.YandexDocumentProcessingStorage(),
                upload_to="partner_agreements/",
                validators=[
                    FileExtensionValidator(allowed_extensions=("docx", "pdf")),
                    core.models.validate_partner_agreement_size,
                ],
                verbose_name="Файл договора",
            ),
        ),
        migrations.RunPython(seed_partner_content, migrations.RunPython.noop),
    ]
