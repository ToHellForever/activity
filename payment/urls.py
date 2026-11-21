from django.urls import path
from . import views


urlpatterns = [
    path("create-payment/<int:ticket_id>/", views.create_payment, name="create_payment"),
    path("bulk-buy/<int:event_id>/", views.bulk_buy_tickets, name="bulk_buy_tickets"),
    path("handle_package_change_choice/", views.handle_package_change_choice, name="handle_package_change_choice"),
    path("create_invoice/<int:package_id>/", views.create_invoice, name="create_invoice"),
    path("robokassa/result/", views.robokassa_result, name="robokassa_result"),
    path("robokassa/success/", views.robokassa_success, name="robokassa_success"),
    path("robokassa/fail/", views.robokassa_fail, name="robokassa_fail"),
    path("success/<int:order_id>/", views.payment_success, name="payment_success"),
    path("refund/<int:order_id>/<int:order_ticket_id>/", views.refund_ticket, name="refund_ticket"),
    path("refund/<int:order_id>/", views.refund_ticket, name="refund_ticket_legacy"),
    path("pay-reserved/<int:order_id>/", views.pay_reserved_order, name="pay_reserved_order"),
]
