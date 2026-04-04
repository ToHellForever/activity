from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views
from core import views

urlpatterns = [
    path('admin/', admin.site.urls),
    # регистраиця
    path('login/', views.login_view, name='login'), # Страница входа
    # выход
    path('logout/', views.custom_logout, name='logout'),
    path('register/', views.register_view, name='register'), # Страница регистрации
    # личный профиль пользователя
    path('visitor/', include('visitor_app.urls', namespace='visitor')),
    # личный профиль партнера
    path('partner/', include('partner_app.urls', namespace='partner')),
] 