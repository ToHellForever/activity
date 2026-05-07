from django.urls import path
from . import views

app_name = "venues"

urlpatterns = [
    path("get_equipment_items/", views.get_equipment_items, name="get_equipment_items"),
    path("save_venue_equipment/", views.save_venue_equipment, name="save_venue_equipment"),
    path("venue/<int:venue_id>/get_equipment_items/", views.get_venue_equipment, name="get_venue_equipment"),
    path('', views.VenueListView.as_view(), name='venue_list'),
    path('<slug:slug>/', views.VenueDetailView.as_view(), name='venue_detail'),
]
