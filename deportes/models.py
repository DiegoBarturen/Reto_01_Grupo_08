from django.db import models
from django.utils import timezone
from decimal import Decimal

class Evento(models.Model):
    OPCIONES_DEPORTE = [
        ('FUTBOL', '⚽ Fútbol'),
        ('BASKET', '🏀 Baloncesto'),
        ('TENIS', '🎾 Tenis'),
        ('ESPORTS', '🎮 eSports'),
        ('UFC', '🥊 UFC / Boxeo'),
    ]
    ESTADOS_PARTIDO = [
        ('PENDIENTE', 'Pendiente de inicio'),
        ('EN_JUEGO', 'En Juego (En vivo)'),
        ('FINALIZADO', 'Finalizado'),
        ('SUSPENDIDO', 'Suspendido')
    ]
    
    deporte = models.CharField(max_length=20, choices=OPCIONES_DEPORTE, default='FUTBOL')
    equipo_local = models.CharField(max_length=100, verbose_name="Equipo Local")
    equipo_visitante = models.CharField(max_length=100, verbose_name="Equipo Visitante")
    fecha_hora = models.DateTimeField(verbose_name="Fecha y Hora del Partido", default=timezone.now)
    estado = models.CharField(max_length=20, choices=ESTADOS_PARTIDO, default='PENDIENTE')
    
    class Meta:
        verbose_name = "Evento Deportivo"
        verbose_name_plural = "Eventos Deportivos"
        
    def __str__(self):
        return f"[{self.get_deporte_display()}] {self.equipo_local} vs {self.equipo_visitante}"

class Cuota(models.Model):
    evento = models.OneToOneField(Evento, on_delete=models.CASCADE, related_name='cuotas')
    paga_local = models.DecimalField(max_digits=5, decimal_places=2, default=1.00, verbose_name="Cuota Local (1)")
    paga_empate = models.DecimalField(max_digits=5, decimal_places=2, default=1.00, verbose_name="Cuota Empate (X)")
    paga_visitante = models.DecimalField(max_digits=5, decimal_places=2, default=1.00, verbose_name="Cuota Visitante (2)")
    
    class Meta:
        verbose_name = "Cuota del Evento"
        verbose_name_plural = "Cuotas de los Eventos"
        
    def __str__(self):
        return f"Cuotas para: {self.evento}"

    def obtener_cuota_actual(self, seleccion):
        """
        Retorna la cuota real desde la BD según la selección del usuario.
        Sirve para validar si la cuota que el JS envió es la misma que está en la DB.
        """
        if seleccion == 'LOCAL': return self.paga_local
        if seleccion == 'EMPATE': return self.paga_empate
        if seleccion == 'VISITANTE': return self.paga_visitante
        return Decimal('0.00')