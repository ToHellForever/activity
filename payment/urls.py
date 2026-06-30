from django.urls import path
from . import views


urlpatterns = [
    path("create-payment/<int:ticket_id>/", views.create_payment, name="create_payment"),
    path("bulk-buy/<int:event_id>/", views.bulk_buy_tickets, name="bulk_buy_tickets"),
    path("create_package_payment/<int:package_id>/", views.create_package_payment, name="create_package_payment"),
    path("handle_package_change_choice/", views.handle_package_change_choice, name="handle_package_change_choice"),
    path("create_invoice/<int:package_id>/", views.create_invoice, name="create_invoice"),
    path("webhook/", views.yookassa_webhook, name="yookassa_webhook"),
    path("package_success/<int:package_id>/", views.package_success, name="package_success"),
    path("success/<int:order_id>/", views.payment_success, name="payment_success"),
    path('refund/<int:order_id>/', views.refund_ticket, name='refund_ticket'),
    path("pay-reserved/<int:order_id>/", views.pay_reserved_order, name="pay_reserved_order"),
]
