from django.urls import path
from . import views

app_name = 'deportes'

urlpatterns = [
    path('', views.cartelera, name='cartelera'),
    # Nueva ruta protegida para el administrador
    path('crear/', views.crear_partido, name='crear_partido'),
]