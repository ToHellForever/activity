from django.urls import path
from . import views

app_name = "visitor"

urlpatterns = [
    path("dashboard/", views.visitor_dashboard, name="dashboard"),
    path("change-password/", views.change_password, name="change_password"),
]
