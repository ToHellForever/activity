from . import views
from django.urls import path
app_name = 'visitor'

urlpatterns = [
    path('dashboard/', views.visitor_dashboard, name='dashboard'),
]