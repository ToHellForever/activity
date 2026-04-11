from django.urls import path
from . import views

app_name = 'partner' 

urlpatterns = [
    # dashboard
    path('dashboard/', views.partner_dashboard, name='dashboard'), 
    path('event/create/', views.create_event, name='create_event'), 
    path('partner_events/', views.partner_event_list, name='partner_event_list'), 
    path('event/<int:event_id>/edit/', views.edit_event, name='edit_event'),
    path('reports/', views.reports, name='reports'),
    path('event/<int:event_id>/participants/', views.participant_list, name='participant_list'),
    path('finances/', views.finances, name='finances'), 
    path('profile/', views.profile_edit, name='profile_edit'),
]