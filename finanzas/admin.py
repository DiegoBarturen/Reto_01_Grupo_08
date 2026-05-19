from django.contrib import admin

from .models import Auditoria, Billetera, Transaccion


@admin.register(Billetera)
class BilleteraAdmin(admin.ModelAdmin):
    list_display = ("usuario", "saldo", "actualizado_en", "creado_en")
    search_fields = ("usuario__username", "usuario__email")


@admin.register(Transaccion)
class TransaccionAdmin(admin.ModelAdmin):
    list_display = ("billetera", "tipo", "metodo", "monto", "creado_en")
    list_filter = ("tipo", "metodo", "creado_en")
    search_fields = ("billetera__usuario__username", "descripcion")


@admin.register(Auditoria)
class AuditoriaAdmin(admin.ModelAdmin):
    list_display = ("accion", "usuario", "creado_en")
    list_filter = ("accion", "creado_en")
    search_fields = ("usuario__username", "detalle")
