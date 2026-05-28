from django.contrib import admin
from .models import Perfil, Billetera, LedgerEntry

@admin.register(Perfil)
class PerfilAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'dni', 'estado', 'limite_deposito_diario')
    list_filter = ('estado',)

@admin.register(Billetera)
class BilleteraAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'tipo', 'saldo_actual', 'creado_en')

    def saldo_actual(self, obj):
        return obj.saldo 
    saldo_actual.short_description = 'Saldo (Calculado)'

@admin.register(LedgerEntry)
class LedgerEntryAdmin(admin.ModelAdmin):
    list_display = ('billetera', 'direccion', 'monto', 'creado_en')
    list_filter = ('direccion', 'billetera__tipo')
    search_fields = ('descripcion',)