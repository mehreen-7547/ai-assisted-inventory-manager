from django.urls import path
from . import views

urlpatterns = [
    path('suppliers/', views.supplier_list, name='supplier_list'),
    path('suppliers/add/', views.supplier_create, name='supplier_create'),
    path('suppliers/<int:supplier_id>/edit/', views.supplier_edit, name='supplier_edit'),

    path(
        'suppliers/<int:supplier_id>/status/',
        views.toggle_supplier_status,
        name='toggle_supplier_status'
    ),


]