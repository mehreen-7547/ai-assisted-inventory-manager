
from django.urls import path

from . import views


urlpatterns = [
    path(
        'add/',
        views.purchase_order_create,
        name='purchase_order_create'
    ),
    path(
        'purchase-orders/',
        views.purchase_order_list,
        name='purchase_order_list'
    ),
    path(
        'purchase-orders/<int:pk>/',
        views.purchase_order_detail,
        name='purchase_order_detail'
    ),
    path(
        'purchase-orders/<int:pk>/status/',
        views.purchase_order_status,
        name='purchase_order_status'
    ),
    path(
        'purchase-orders/<int:pk>/receive/',
        views.goods_receipt_create,
        name='goods_receipt_create'
    ),
]
