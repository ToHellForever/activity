from django.urls import path
from . import views


urlpatterns = [
    path("create-payment/<int:ticket_id>/", views.create_payment, name="create_payment"),
    path("create_package_payment/<int:package_id>/", views.create_package_payment, name="create_package_payment"),
    path("webhook/", views.yookassa_webhook, name="yookassa_webhook"),
    path("success/<int:order_id>/", views.payment_success, name="payment_success"),
    path('refund/<int:order_id>/', views.refund_ticket, name='refund_ticket'),
    path("pay-reserved/<int:order_id>/", views.pay_reserved_order, name="pay_reserved_order"),
]
