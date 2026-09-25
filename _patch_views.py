from pathlib import Path

path = Path("core/views.py")
src = path.read_text(encoding="utf-8")

replacements = [
    (
        '''def privacy_policy_view(request):
    """Политика конфиденциальности"""
    return render(request, "other/privacy_policy.html")''',
        '''def privacy_policy_view(request):
    """Политика конфиденциальности"""
    return render(request, "other/privacy_policy.html", {
        "content": legal_pages.get_content("privacy-policy"),
    })''',
    ),
    (
        '''def offer_view(request):
    """Публичная оферта"""
    return render(request, "other/offer.html")''',
        '''def offer_view(request):
    """Публичная оферта"""
    return render(request, "other/offer.html", {
        "content_participant": legal_pages.get_content("offer-participant"),
        "content_organizer": legal_pages.get_content("offer-organizer"),
        "content_venue": legal_pages.get_content("offer-venue"),
    })''',
    ),
    (
        '''def personal_data_consent_view(request):
    """Страница согласия на обработку персональных данных."""
    return render(request, "other/consent_personal_data.html")''',
        '''def personal_data_consent_view(request):
    """Страница согласия на обработку персональных данных."""
    return render(request, "other/consent_personal_data.html", {
        "content": legal_pages.get_content("personal-data-consent"),
    })''',
    ),
    (
        '''def mailing_consent_view(request):
    """Страница согласия на рассылку."""
    return render(request, "other/consent_mailing.html")''',
        '''def mailing_consent_view(request):
    """Страница согласия на рассылку."""
    return render(request, "other/consent_mailing.html", {
        "content": legal_pages.get_content("mailing-consent"),
    })''',
    ),
]

for old, new in replacements:
    if old not in src:
        raise SystemExit("NOT FOUND:\n" + old[:80])
    src = src.replace(old, new, 1)

path.write_text(src, encoding="utf-8")
print("OK: views updated")
