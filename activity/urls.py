from django.contrib import admin
from django.contrib.sitemaps.views import sitemap
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.shortcuts import render
from core.views import (
    landing_page,
    login_view,
    register_view,
    custom_logout,
    support_dashboard,
    moderator_dashboard,
    send_support_message,
    search_users_for_ticket,
    moderator_create_ticket,
    event_list,
    event_detail,
    send_event_request,
    activate_account,
    forgot_password,
    reset_password,
    update_ticket_status,
    sales_register,
    verify_email_view,
    resend_verification_code,
    check_ticket,
    privacy_policy_view,
    offer_view,
    faq_view,
    contacts_view,
    about_view,
    robots_txt,
    organizer_contract_download,
    personal_data_consent_view,
    mailing_consent_view,
)
from core.sitemaps import StaticViewSitemap, EventSitemap, VenueSitemap
from partner_app.views import (
    scanner_view,
    scanner_scan,
    scanner_end_shift,
)


def _dev_refund_error(request):
    return render(request, "payment/refund_error.html", {"error": "Произошла ошибка при обработке возврата. Попробуйте ещё раз или свяжитесь с нашей службой поддержки."})


def _dev_refund_success(request):
    return render(request, "payment/refund_success.html", {})


def _dev_refund_success_free(request):
    return render(request, "payment/refund_success_free.html", {})


sitemaps = {
    "static": StaticViewSitemap,
    "events": EventSitemap,
    "venues": VenueSitemap,
}

app_name = "venues"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", landing_page, name="landing_page"),
    path("login/", login_view, name="login"),
    path("register/", register_view, name="register"),
    path("logout/", custom_logout, name="logout"),
    path("support/", support_dashboard, name="support_dashboard"),
    path("moderator/", moderator_dashboard, name="moderator_dashboard"),
    path("send-message/", send_support_message, name="send_support_message"),
    path("moderator/search-users/", search_users_for_ticket, name="search_users_for_ticket"),
    path("moderator/create-ticket/", moderator_create_ticket, name="moderator_create_ticket"),
    path("events/", event_list, name="event_list"),
    path("events/<int:event_id>/", event_detail, name="event_detail"),
    path(
        "send-event-request/<int:event_id>/",
        send_event_request,
        name="send_event_request",
    ),
    path("activate/<str:token>/", activate_account, name="activate_account"),
    path("forgot-password/", forgot_password, name="forgot_password"),
    path("reset-password/<str:token>/", reset_password, name="reset_password"),
    path("verify-email/", verify_email_view, name="verify_email"),
    path("resend-verification-code/", resend_verification_code, name="resend_verification_code"),
    path(
        "update-ticket-status/<int:ticket_id>/",
        update_ticket_status,
        name="update_ticket_status",
    ),
    path("partner/", include("partner_app.urls")),
    path("visitor/", include("visitor_app.urls")),
    path("venues/", include("venues.urls")),
    path("admin/venues/", include("venues.urls", namespace="admin_venues")),
    path("check-ticket/<int:order_id>/", check_ticket, name="check_ticket"),
    path("reports/sales-register/", sales_register, name="sales_register"),
    path("payment/", include(("payment.urls", "payment"), namespace="payment")),
    path("scanner/<str:access_code>/", scanner_view, name="scanner_view"),
    path("scanner/<str:access_code>/scan/", scanner_scan, name="scanner_scan"),
    path("scanner/<str:access_code>/end-shift/", scanner_end_shift, name="scanner_end_shift"),
    # Статические страницы
    path("privacy-policy/", privacy_policy_view, name="privacy_policy"),
    path("offer/", offer_view, name="offer"),
    path("documents/organizer-contract/", organizer_contract_download, name="organizer_contract_download"),
    path("documents/personal-data-consent/", personal_data_consent_view, name="personal_data_consent_view"),
    path("documents/mailing-consent/", mailing_consent_view, name="mailing_consent_view"),
    path("faq/", faq_view, name="faq"),
    path("contacts/", contacts_view, name="contacts"),
    path("about/", about_view, name="about"),
    # SEO: robots.txt и sitemap.xml
    path("robots.txt", robots_txt, name="robots_txt"),
    path(
        "sitemap.xml",
        sitemap,
        {"sitemaps": sitemaps},
        name="django.contrib.sitemaps.views.sitemap",
    ),
    # DEV: локальные страницы для просмотра стилей
    path("dev/refund-error/", _dev_refund_error, name="dev_refund_error"),
    path("dev/refund-success/", _dev_refund_success, name="dev_refund_success"),
    path("dev/refund-success-free/", _dev_refund_success_free, name="dev_refund_success_free"),
]


if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
