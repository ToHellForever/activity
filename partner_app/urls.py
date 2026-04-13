from django.urls import path
from . import views

app_name = "partner"

urlpatterns = [
    path("dashboard/", views.partner_dashboard, name="dashboard"),
    path("create_event/", views.create_event, name="create_event"),
    path("edit_event/<int:event_id>/", views.edit_event, name="edit_event"),
    path("events/", views.partner_event_list, name="partner_event_list"),
    path("reports/", views.reports, name="reports"),
    path("participants/<int:event_id>/", views.participant_list, name="participant_list"),
    path("finances/", views.finances, name="finances"),
    path("profile/", views.profile_edit, name="profile_edit"),
    path("change_password/", views.change_password, name="change_password"),
]