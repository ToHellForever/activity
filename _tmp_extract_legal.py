"""Временный скрипт: достаёт тексты юридических страниц из старых шаблонов."""
import io
import re
import pathlib

OUT = pathlib.Path("core/legal_documents_defaults")
OUT.mkdir(parents=True, exist_ok=True)

# Старые шаблоны: (файл, регулярка с телом документа, имя файла результата)
SOURCES = [
    ("templates/other/offer.html", r'<div class="offer-content"[^>]*data-policy-content="participant"[^>]*>(.*?)\n</div>\n', "offer-participant.html"),
    ("templates/other/offer.html", r'<div class="offer-content"[^>]*data-policy-content="visitor"[^>]*>(.*?)\n</div>\n', "offer-visitor.html"),
    ("templates/other/offer.html", r'<div class="offer-content"[^>]*data-policy-content="organizer"[^>]*>(.*?)\n</div>\n', "offer-organizer.html"),
    ("templates/other/privacy_policy.html", r'<div class="policy-content">(.*?)\n        </div>\n    </div>', "privacy-policy.html"),
    ("templates/other/consent_personal_data.html", r'<div class="policy-content">(.*?)\n        </div>\n    </div>', "personal-data-consent.html"),
    ("templates/other/consent_mailing.html", r'<div class="policy-content">(.*?)\n        </div>\n    </div>', "mailing-consent.html"),
]

for template, pattern, target_name in SOURCES:
    target = OUT / target_name
    if target.exists() and target.stat().st_size > 500:
        print("skip (уже есть):", target_name, target.stat().st_size)
        continue
    html = io.open(template, encoding="utf-8").read()
    match = re.search(pattern, html, re.S)
    if not match:
        print("НЕ НАЙДЕНО в", template, "->", target_name)
        continue
    body = match.group(1).strip() + "\n"
    io.open(target, "w", encoding="utf-8", newline="\n").write(body)
    print("ok:", target_name, len(body), body[:60].replace("\n", " "))
