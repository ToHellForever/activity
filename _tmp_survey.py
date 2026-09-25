import io
import os

print("=== files exist? ===")
for p in [
    "core/legal_pages.py",
    "core/tests/test_legal_pages.py",
    "core/legal_documents_seed.py",
    "core/migrations/0044_legaldocument_seed.py",
    "templates/legal",
    "_tmp_extract_legal.py",
    "_tmp_extract_offers.py",
]:
    print(f"  {p}: {os.path.exists(p)}")

print("=== LegalDocument model ===")
lines = io.open("core/models.py", encoding="utf-8").read().split("\n")
start = next(i for i, l in enumerate(lines) if l.startswith("class LegalDocument"))
print(f"(строка {start + 1})")
for i in range(start, min(start + 60, len(lines))):
    print(f"{i + 1}: {lines[i]}")
