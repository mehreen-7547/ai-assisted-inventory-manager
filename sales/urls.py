
from django.urls import path
from . import views

urlpatterns = [
    path(
        'sales/add/',
        views.sale_create,
        name='sale_create'
    ),
    path(
        'sales/<int:sale_id>/',
        views.sale_detail,
        name='sale_detail'
    ),
]
