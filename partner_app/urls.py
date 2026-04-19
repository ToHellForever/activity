from django.urls import path
from . import views

app_name = "partner"

urlpatterns = [
    path("dashboard/", views.partner_dashboard, name="dashboard"),
    path("create_event/", views.create_event, name="create_event"),
    path("edit_event/<int:event_id>/", views.edit_event, name="edit_event"),
    path("partner_event_list/", views.partner_event_list, name="partner_event_list"),
    path(
        "duplicate_event/<int:event_id>/", views.duplicate_event, name="duplicate_event"
    ),
    path("delete_event/<int:event_id>/", views.delete_event, name="delete_event"),
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
        "mark_attendance/<int:event_id>/<int:order_id>/",
        views.mark_attendance,
        name="mark_attendance",
    ),
    path(
        "check_ticket/<int:order_id>/",
        views.check_ticket,
        name="check_ticket",
    ),
]
