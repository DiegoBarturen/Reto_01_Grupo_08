from django.urls import path
from .api_views import api_crear_apuesta, api_listar_mis_apuestas
from . import views

app_name = 'apuestas'

urlpatterns = [
    path('pendientes/', views.lista_pendientes, name='lista_pendientes'),
    path('liquidar/<int:apuesta_id>/<str:resultado>/', views.liquidar_apuesta, name='liquidar_apuesta'),
    path('apostar/', views.realizar_apuesta, name='realizar_apuesta'),
    path('api/crear/', api_crear_apuesta, name='api_crear_apuesta'),
    path('api/mis-apuestas/', api_listar_mis_apuestas, name='api_listar_mis_apuestas'),
]
