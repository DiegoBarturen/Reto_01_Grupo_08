from django.contrib import admin
from .models import Evento, Cuota

# Esto permite que las cuotas se editen dentro de la misma pantalla del Evento
class CuotaInline(admin.StackedInline):
    model = Cuota
    can_delete = False
    verbose_name_plural = 'Cuotas del Partido'

@admin.register(Evento)
class EventoAdmin(admin.ModelAdmin):
    # Columnas que se verán en la lista principal
    list_display = ('equipo_local', 'equipo_visitante', 'fecha_hora', 'estado')
    # Filtros laterales
    list_filter = ('estado', 'fecha_hora')
    # Barra de búsqueda
    search_fields = ('equipo_local', 'equipo_visitante')
    # Integra las cuotas en la vista del evento
    inlines = [CuotaInline]