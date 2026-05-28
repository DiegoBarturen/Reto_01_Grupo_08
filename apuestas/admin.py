from django.contrib import admin
from .models import Apuesta

@admin.register(Apuesta)
class ApuestaAdmin(admin.ModelAdmin):
    # Configuración de las columnas que verás en la lista
    list_display = ('id', 'usuario', 'evento', 'seleccion', 'monto_apostado', 'cuota_fijada', 'estado', 'fecha_creacion')
    
    # Filtros laterales para buscar rápido
    list_filter = ('estado', 'fecha_creacion')
    
    # Buscador en la parte superior
    search_fields = ('usuario__username', 'evento__equipo_local', 'evento__equipo_visitante')
    
    # Campos que el admin no debería poder cambiar a la ligera por seguridad
    readonly_fields = ('fecha_creacion', 'cuota_fijada', 'monto_apostado')
    
    # Ordenar por los más nuevos
    ordering = ('-fecha_creacion',)

    # Opcional: Esto ayuda a que el admin vea la relación completa
    raw_id_fields = ('usuario', 'evento')