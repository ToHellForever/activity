from django.urls import path
from . import views

app_name = "partner"

urlpatterns = [
    path("dashboard/", views.partner_dashboard, name="dashboard"),
    path("create_event/", views.create_event, name="create_event"),
    path("edit_event/<int:event_id>/", views.edit_event, name="edit_event"),
    path("partner_event_list/", views.partner_event_list, name="partner_event_list"),
    path("delete_event/<int:event_id>/", views.delete_event, name="delete_event"),
    path("bulk_delete_events/", views.bulk_delete_events, name="bulk_delete_events"),
    path("reports/", views.reports, name="reports"),
    path("reports/generate/", views.generate_report, name="generate_report"),
    path("report_schedule/", views.report_schedule, name="report_schedule"),
    path(
        "participant_list/<int:event_id>/",
        views.participant_list,
        name="participant_list",
    ),
    path("finances/", views.finances, name="finances"),
    path("profile_edit/", views.profile_edit, name="profile_edit"),
    path(
        "mark_attendance/<int:event_id>/<int:order_id>/<int:ticket_number>/",
        views.mark_attendance,
        name="mark_attendance",
    ),
    path(
        "mark_attendance/<int:event_id>/<int:order_id>/",
        views.mark_attendance,
        name="mark_attendance_legacy",
    ),
    path(
        "remove_media/<str:media_type>/<int:media_id>/",
        views.remove_media,
        name="remove_media",
    ),
    path("request_payout/", views.request_payout, name="request_payout"),
    path("payout-details/", views.payout_details, name="payout_details"),
    path("payout-details/set-default/", views.set_default_payout_detail, name="set_default_payout_detail"),
    path("delete_reports/", views.delete_reports, name="delete_reports"),
    path("change-password/", views.change_password, name="change_password"),
    path("remove_event_image/<int:image_id>/", views.remove_event_image, name="remove_event_image"),
    path("set_primary_image/<int:image_id>/", views.set_primary_image, name="set_primary_image"),
    path("save_field/", views.save_field, name="save_field"),
    # Портфолио
    path("portfolio/", views.portfolio_list, name="portfolio_list"),
    path("portfolio/create/", views.portfolio_create, name="portfolio_create"),
    path("portfolio/edit/<int:item_id>/", views.portfolio_edit, name="portfolio_edit"),
    path("portfolio/delete/<int:item_id>/", views.portfolio_delete, name="portfolio_delete"),
    path("portfolio/image/delete/<int:image_id>/", views.portfolio_image_delete, name="portfolio_image_delete"),
     # Чаты участников по мероприятиям
     path("chats/", views.partner_chats, name="chats"),
     path("chats_list/", views.partner_chats_list, name="chats_list"),
    # Контроль входа
    path("entry-control/<int:event_id>/enable/", views.enable_entry_control, name="enable_entry_control"),
    path("entry-control/<int:link_id>/toggle/", views.toggle_entry_control, name="toggle_entry_control"),
    path("entry-control/<int:link_id>/delete/", views.delete_entry_control, name="delete_entry_control"),
    path("entry-control/<int:event_id>/status/", views.entry_control_status, name="entry_control_status"),
]
