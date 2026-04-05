from django.urls import path
from . import views

app_name = 'partner' 

urlpatterns = [
    # dashboard
    path('dashboard/', views.partner_dashboard, name='dashboard'), 
    path('event/create/', views.create_event, name='create_event'), 
    path('events/', views.event_list, name='event_list'), 
    path('reports/', views.reports, name='reports'),
    path('event/<int:event_id>/participants/', views.participant_list, name='participant_list'),
    path('finances/', views.finances, name='finances'), 
    path('profile/', views.profile_edit, name='profile_edit'),
]