from django.urls import path
from . import views
from payment import views as payment_views

app_name = "visitor"

urlpatterns = [
    path("dashboard/", views.visitor_dashboard, name="dashboard"),
    path("order-history/", views.visitor_order_history, name="order_history"),
    path("change-password/", views.change_password, name="change_password"),
    path("buy-ticket/<int:ticket_id>/", views.buy_ticket, name="buy_ticket"),
    path("refund-ticket/<int:order_id>/", payment_views.refund_ticket, name="refund_ticket"),
    path("chats/", views.visitor_chats, name="chats"),
    path("chats_list/", views.visitor_chats_list, name="chats_list"),
    path("ticket/<int:order_id>/display/", views.display_ticket, name="display_ticket"),
    path("ticket/<int:order_id>/qr/", views.ticket_qr, name="ticket_qr"),
    
]
