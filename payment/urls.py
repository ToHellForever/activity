from django.urls import path
from . import views

urlpatterns = [
    path('create_payment/<int:ticket_id>/', views.create_payment, name='create_payment'),
    path('webhook/', views.yookassa_webhook, name='yookassa_webhook'),
    path('refund/<int:order_id>/', views.refund_ticket, name='refund_ticket'),
    path('success/<int:order_id>/', views.payment_success, name='payment_success'),
]