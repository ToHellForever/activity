from django.urls import path
from . import views

urlpatterns = [
    path('', views.VenueListView.as_view(), name='venue_list'),
    path('<slug:slug>/', views.VenueDetailView.as_view(), name='venue_detail'),
]