from django.urls import path

from . import views


urlpatterns = [
    path(
        'add/',
        views.purchase_order_create,
        name='purchase_order_create'
    ),
]
