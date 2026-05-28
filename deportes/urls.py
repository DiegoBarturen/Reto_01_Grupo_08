from django.urls import path
from .api_views import (
    api_actualizar_cuotas,
    api_actualizar_evento,
    api_crear_evento,
    api_detalle_evento,
    api_listar_eventos,
)
from . import views 
from apuestas.views import lista_pendientes

app_name = 'deportes'

urlpatterns = [
    path('', views.cartelera, name='cartelera'),
    path('dashboard/', views.dashboard_admin, name='dashboard_admin'),
    path('crear/', views.crear_partido, name='crear_partido'),
    path('pendientes/', lista_pendientes, name='lista_pendientes'),
    path('api/cuotas/', views.api_obtener_cuotas, name='api_cuotas'),
    path('api/eventos/', api_listar_eventos, name='api_listar_eventos'),
    path('api/eventos/crear/', api_crear_evento, name='api_crear_evento'),
    path('api/eventos/<int:evento_id>/', api_detalle_evento, name='api_detalle_evento'),
    path('api/eventos/<int:evento_id>/actualizar/', api_actualizar_evento, name='api_actualizar_evento'),
    path('api/eventos/<int:evento_id>/cuotas/', api_actualizar_cuotas, name='api_actualizar_cuotas'),
    path('gestion/', views.gestionar_eventos, name='gestionar_eventos'),
    path('gestion/editar/<int:evento_id>/', views.editar_evento, name='editar_evento'),
    path('gestion/eliminar/<int:evento_id>/', views.eliminar_evento, name='eliminar_evento'),
]
