from django.urls import path
from . import views

app_name = "partner"

urlpatterns = [
    path('', views.partner_dashboard, name='dashboard'),
    path('profile/edit/', views.profile_edit, name='profile_edit'),
    path('finances/', views.finances, name='finances'),
    path('reports/', views.reports, name='reports'),
    path('event/create/', views.create_event, name='create_event'),
    path('partner_events/', views.partner_event_list, name='partner_event_list'),
    path('event/<int:event_id>/edit/', views.edit_event, name='edit_event'),
    path('event/<int:event_id>/duplicate/', views.duplicate_event, name='duplicate_event'),
    path('event/<int:event_id>/delete/', views.delete_event, name='delete_event'),
    path('event/<int:event_id>/participants/', views.participant_list, name='participant_list'),
]