from django.urls import path
from . import views

app_name = 'partner' 

urlpatterns = [
    path('', views.event_list, name='event_list'), 
]