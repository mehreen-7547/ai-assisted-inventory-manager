
from django.urls import path
from . import views


urlpatterns = [
    path(
        'intelligence/',
        views.intelligence_dashboard,
        name='intelligence_dashboard'
    ),
]
