from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models


class Billetera(models.Model):
    usuario = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="billetera",
    )
    saldo = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    actualizado_en = models.DateTimeField(auto_now=True)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Billetera"
        verbose_name_plural = "Billeteras"

    def __str__(self):
        return f"Billetera de {self.usuario.username}"


class Transaccion(models.Model):
    class Tipo(models.TextChoices):
        RECARGA = "RECARGA", "Recarga"
        RETIRO = "RETIRO", "Retiro"

    class Metodo(models.TextChoices):
        TARJETA = "TARJETA", "Tarjeta virtual"
        TRANSFERENCIA = "TRANSFERENCIA", "Transferencia simulada"
        YAPE_PLIN = "YAPE_PLIN", "Yape o Plin simulado"

    billetera = models.ForeignKey(
        Billetera,
        on_delete=models.CASCADE,
        related_name="transacciones",
    )
    tipo = models.CharField(max_length=20, choices=Tipo.choices)
    metodo = models.CharField(
        max_length=20,
        choices=Metodo.choices,
        default=Metodo.TARJETA,
    )
    monto = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    descripcion = models.CharField(max_length=255, blank=True)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Transaccion"
        verbose_name_plural = "Transacciones"
        ordering = ["-creado_en"]

    def __str__(self):
        return f"{self.tipo} - {self.metodo} - S/ {self.monto}"


class Auditoria(models.Model):
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="auditorias",
        null=True,
        blank=True,
    )
    accion = models.CharField(max_length=100)
    detalle = models.TextField()
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Auditoria"
        verbose_name_plural = "Auditorias"
        ordering = ["-creado_en"]

    def __str__(self):
        return f"{self.accion} - {self.creado_en:%Y-%m-%d %H:%M}"
