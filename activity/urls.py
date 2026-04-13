from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views
from core import views
from partner_app import views as partner_views
from django.conf.urls.static import static
# settings
from django.conf import settings

urlpatterns = [
    path('admin/', admin.site.urls),
    path("", views.landing_page, name="landing_page"),
    path('partner/', include('partner_app.urls', namespace='partner')), 
    path('visitor/', include('visitor_app.urls', namespace='visitor')), 
    # регистраиця
    path('login/', views.login_view, name='login'), # Страница входа
    # выход
    path('logout/', views.custom_logout, name='logout'),
    path('register/', views.register_view, name='register'), # Страница регистрации
    path('moderator/', views.moderator_dashboard, name='moderator_dashboard'), # Страница модератора
    path('support/send/', views.send_support_message, name='send_support_message'), # Страница отправки сообщения
    path('support/', views.support_dashboard, name='support_dashboard'), # Страница поддержки
    path('upload-image/', views.upload_image, name='upload_image'), # Страница загрузки изображения
    path('ticket/update-status/<int:ticket_id>/', views.update_ticket_status, name='update_ticket_status'), # Страница обновления статуса билета
    path("events/", views.event_list, name="event_list"),  # Страница списка событий
    path("events/<int:event_id>/", views.event_detail, name="event_detail"),  # Страница детального описания события
    path("events/<int:event_id>/buy/", views.buy_ticket, name="buy_ticket"),  # Страница покупки билета
    path("activate/<int:pk>/", views.activate_account, name="activate_account"), # Страница активации аккаунта
    path("buy/<int:event_id>/", views.buy_ticket, name="buy_ticket"), # Страница покупки билета
    path("change_password/", views.change_password, name="change_password"),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)