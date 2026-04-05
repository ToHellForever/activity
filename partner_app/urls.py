from django.urls import path
from . import views

app_name = 'partner' 

urlpatterns = [
    # dashboard
    path('dashboard/', views.partner_dashboard, name='dashboard'), 
    path('event/create/', views.create_event, name='create_event'), 
    path('events/', views.event_list, name='event_list'), 
    path('reports/', views.reports, name='reports'),
]