from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from core.views import (
    landing_page,
    login_view,
    register_view,
    custom_logout,
    change_password,
    support_dashboard,
    moderator_dashboard,
    send_support_message,
    event_list,
    event_detail,
    buy_ticket,
    activate_account,
    forgot_password,
    update_ticket_status,
)
app_name = "venues"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", landing_page, name="landing_page"),
    path("login/", login_view, name="login"),
    path("register/", register_view, name="register"),
    path("logout/", custom_logout, name="logout"),
    path("change-password/", change_password, name="change_password"),
    path("support/", support_dashboard, name="support_dashboard"),
    path("moderator/", moderator_dashboard, name="moderator_dashboard"),
    path("send-message/", send_support_message, name="send_support_message"),
    path("events/", event_list, name="event_list"),
    path("events/<int:event_id>/", event_detail, name="event_detail"),
    path("buy-ticket/<int:event_id>/", buy_ticket, name="buy_ticket"),
    path("activate/<int:pk>/", activate_account, name="activate_account"),
    path("forgot-password/", forgot_password, name="forgot_password"),
    path("update-ticket-status/<int:ticket_id>/", update_ticket_status, name="update_ticket_status"),
    path("partner/", include("partner_app.urls")),
    path("visitor/", include("visitor_app.urls")),
    path("venues/", include("venues.urls")),
    path("admin/venues/", include("venues.urls", namespace="admin_venues")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
