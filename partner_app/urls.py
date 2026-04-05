from django.urls import path
from . import views

app_name = 'partner' 

urlpatterns = [
    # dashboard
    path('dashboard/', views.partner_dashboard, name='dashboard'), 
    path('events/', views.event_list, name='event_list'), 
]