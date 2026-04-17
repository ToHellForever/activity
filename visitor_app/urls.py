from django.urls import path
from . import views

app_name = "visitor"

urlpatterns = [
    path("dashboard/", views.visitor_dashboard, name="dashboard"),
    path("refund/<int:order_id>/", views.refund_ticket, name="refund_ticket"),
]
