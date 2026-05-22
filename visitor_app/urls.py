from django.urls import path
from . import views
from payment import views as payment_views

app_name = "visitor"

urlpatterns = [
    path("dashboard/", views.visitor_dashboard, name="dashboard"),
    path("change-password/", views.change_password, name="change_password"),
    path("buy-ticket/<int:ticket_id>/", views.buy_ticket, name="buy_ticket"),
    path("refund-ticket/<int:order_id>/", payment_views.refund_ticket, name="refund_ticket"),
]
