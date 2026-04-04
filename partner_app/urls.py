from django.urls import path
from . import views

app_name = 'partner' 

urlpatterns = [
    path('dashboard/', views.partner_dashboard, name='dashboard'),
]