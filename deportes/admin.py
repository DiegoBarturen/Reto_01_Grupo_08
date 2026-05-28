from django.contrib import admin
from .models import Evento, Cuota

class CuotaInline(admin.StackedInline):
    model = Cuota
    can_delete = False
    verbose_name_plural = 'Cuotas del Partido'

@admin.register(Evento)
class EventoAdmin(admin.ModelAdmin):
    list_display = ('equipo_local', 'equipo_visitante', 'deporte', 'fecha_hora', 'estado')
    list_filter = ('estado', 'deporte', 'fecha_hora')
    search_fields = ('equipo_local', 'equipo_visitante')
    inlines = [CuotaInline]