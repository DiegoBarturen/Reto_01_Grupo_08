from django.db import models
from django.contrib.auth.models import User
from django.db.models import Sum
from decimal import Decimal
import uuid

class Perfil(models.Model):
    class Estado(models.TextChoices):
        PENDIENTE = 'PENDIENTE', 'Pendiente de Verificación'
        VERIFICADO = 'VERIFICADO', 'Verificado'
        BLOQUEADO = 'BLOQUEADO', 'Bloqueado'
        AUTOEXCLUIDO = 'AUTOEXCLUIDO', 'Autoexcluido'

    usuario = models.OneToOneField(User, on_delete=models.CASCADE, related_name='perfil')
    dni = models.CharField(max_length=8, unique=True, null=True, blank=True)
    fecha_nacimiento = models.DateField(null=True, blank=True)
    estado = models.CharField(max_length=20, choices=Estado.choices, default=Estado.PENDIENTE)

    limite_deposito_diario = models.DecimalField(max_digits=18, decimal_places=4, default=Decimal('1000.0000'))
    autoexcluido_hasta = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Perfil de {self.usuario.username} - {self.estado}"

class Billetera(models.Model):
    class TipoCuenta(models.TextChoices):
        USUARIO = 'USUARIO', 'Billetera de Usuario'
        CASA = 'CASA', 'Cuenta Matriz de la Casa'
        PENDIENTES = 'PENDIENTES', 'Apuestas Pendientes (Escrow)'
        BONOS = 'BONOS', 'Fondo de Bonos'

    usuario = models.OneToOneField(User, on_delete=models.CASCADE, null=True, blank=True, related_name='billetera')
    tipo = models.CharField(max_length=20, choices=TipoCuenta.choices, default=TipoCuenta.USUARIO)
    creado_en = models.DateTimeField(auto_now_add=True)

    @property
    def saldo(self):
        """
        Cálculo dinámico del saldo: SUM(Créditos) - SUM(Débitos)
        NUNCA se almacena en base de datos.
        """
        creditos = self.movimientos.filter(direccion='CREDIT').aggregate(Sum('monto'))['monto__sum'] or Decimal('0.0000')
        debitos = self.movimientos.filter(direccion='DEBIT').aggregate(Sum('monto'))['monto__sum'] or Decimal('0.0000')
        return creditos - debitos

    def __str__(self):
        if self.usuario:
            return f"Billetera de {self.usuario.username}"
        return f"Cuenta del Sistema: {self.tipo}"

class LedgerEntry(models.Model):
    class Direccion(models.TextChoices):
        DEBIT = 'DEBIT', 'Débito (-)'
        CREDIT = 'CREDIT', 'Crédito (+)'

    billetera = models.ForeignKey(Billetera, on_delete=models.PROTECT, related_name='movimientos')
    transaction_id = models.UUIDField(default=uuid.uuid4, editable=False) 
    direccion = models.CharField(max_length=10, choices=Direccion.choices)
    monto = models.DecimalField(max_digits=18, decimal_places=4)
    descripcion = models.CharField(max_length=255)
    creado_en = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.direccion} | S/ {self.monto} | {self.billetera}"