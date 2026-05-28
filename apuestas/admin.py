from django.contrib import admin
from .models import Apuesta

@admin.register(Apuesta)
class ApuestaAdmin(admin.ModelAdmin):

    list_display = ('id', 'usuario', 'evento', 'seleccion', 'monto_apostado', 'cuota_fijada', 'estado', 'fecha_creacion')
    
    list_filter = ('estado', 'fecha_creacion')
    
    search_fields = ('usuario__username', 'evento__equipo_local', 'evento__equipo_visitante')
    
    readonly_fields = ('fecha_creacion', 'cuota_fijada', 'monto_apostado')
    
    ordering = ('-fecha_creacion',)

    raw_id_fields = ('usuario', 'evento')