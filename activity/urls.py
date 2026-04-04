from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views

urlpatterns = [
    path('admin/', admin.site.urls),
    # регистраиця
    path('accounts/login/', auth_views.LoginView.as_view(template_name='registration/login.html'), name='login'),
    # личный профиль пользователя
    path('visitor/', include('visitor_app.urls', namespace='visitor')),
    # личный профиль партнера
    path('partner/', include('partner_app.urls', namespace='partner')),
] 