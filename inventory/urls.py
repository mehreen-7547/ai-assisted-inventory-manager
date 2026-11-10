
from django.urls import path
from . import views

urlpatterns = [
    path(
        'products/<int:product_id>/adjust/',
        views.stock_adjustment,
        name='stock_adjustment'
    ),
]
