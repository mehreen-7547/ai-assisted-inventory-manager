from django.urls import path
from . import views


urlpatterns = [
    path('suppliers/', views.supplier_list, name='supplier_list'),
]