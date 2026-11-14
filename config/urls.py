from django.contrib import admin
from django.urls import include, path


urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("core.urls")),
    path("", include("accounts.urls")),
    path('', include('catalog.urls')),
    path('', include('inventory.urls')),
    path('', include('sales.urls')),
    path('', include('purchasing.urls')),
    path('', include('intelligence.urls')),
]
