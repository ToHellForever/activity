from django.urls import path
from . import views

app_name = "venues"

urlpatterns = [
    # для админки
    path("get_equipment_items/", views.get_equipment_items, name="get_equipment_items"),
    path("save_venue_equipment/", views.save_venue_equipment, name="save_venue_equipment"),
    path("venue/<int:venue_id>/get_equipment_items/", views.get_venue_equipment, name="get_venue_equipment"),
    # для списка площадок
    path("public/get_equipment_items/", views.public_get_equipment_items, name="public_get_equipment_items"),
    path("public/save_venue_equipment/", views.public_save_venue_equipment, name="public_save_venue_equipment"),
    
    path('', views.VenueListView.as_view(), name='venue_list'),
    path('<slug:slug>/', views.VenueDetailView.as_view(), name='venue_detail'),
]
