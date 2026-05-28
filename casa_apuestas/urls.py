from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path('admin/', admin.site.urls),
    path('deportes/', include('deportes.urls')),
    path('', include('finanzas.urls')),
    path('apuestas/', include('apuestas.urls')),
]