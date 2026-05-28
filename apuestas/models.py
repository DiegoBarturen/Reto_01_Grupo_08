from decimal import Decimal
from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator
from deportes.models import Evento

class Apuesta(models.Model):
    class Estado(models.TextChoices):
        PENDIENTE = 'PENDIENTE', 'Pendiente'
        GANADA = 'GANADA', 'Ganada'
        PERDIDA = 'PERDIDA', 'Perdida'
        ANULADA = 'ANULADA', 'Anulada'

    class Seleccion(models.TextChoices):
        LOCAL = 'LOCAL', 'Gana Local'
        EMPATE = 'EMPATE', 'Empate'
        VISITANTE = 'VISITANTE', 'Gana Visitante'

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='apuestas'
    )
    evento = models.ForeignKey(
        Evento, 
        on_delete=models.PROTECT, 
        related_name='apuestas'
    )
    seleccion = models.CharField(max_length=20, choices=Seleccion.choices)
    monto_apostado = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        validators=[MinValueValidator(Decimal('1.00'))]
    )
    cuota_fijada = models.DecimalField(
        max_digits=6, 
        decimal_places=2,
        help_text="La cuota exacta que compró el usuario en el momento de apostar."
    )
    estado = models.CharField(
        max_length=20, 
        choices=Estado.choices, 
        default=Estado.PENDIENTE
    )
    ganancia_potencial = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        editable=False
    )
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Apuesta"
        verbose_name_plural = "Apuestas"
        ordering = ['-fecha_creacion']

    def save(self, *args, **kwargs):
        # Calcula automáticamente cuánto ganaría antes de guardar en la BD
        self.ganancia_potencial = self.monto_apostado * self.cuota_fijada
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Ticket #{self.id} - {self.usuario.username} - {self.evento}"