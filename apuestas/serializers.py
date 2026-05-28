from decimal import Decimal
from django.utils import timezone
from rest_framework import serializers
from deportes.models import Cuota, Evento
from .models import Apuesta


BETTING_PRECISION = Decimal("0.01")
EVENT_AVAILABLE_STATES = {"PENDIENTE", "DISPONIBLE", "ACTIVO"}


def quantize_bet_amount(value):
    return value.quantize(BETTING_PRECISION)


def get_current_odds(cuotas, seleccion):
    odds_by_selection = {
        Apuesta.Seleccion.LOCAL: cuotas.paga_local,
        Apuesta.Seleccion.EMPATE: cuotas.paga_empate,
        Apuesta.Seleccion.VISITANTE: cuotas.paga_visitante,
    }
    return odds_by_selection.get(seleccion)


def validate_event_accepts_bets(evento):
    if evento.fecha_hora <= timezone.now():
        raise serializers.ValidationError(
            {"evento": "El evento deportivo ya inicio y no acepta nuevas apuestas."}
        )

    if evento.estado.upper() not in EVENT_AVAILABLE_STATES:
        raise serializers.ValidationError(
            {"evento": "El evento deportivo no se encuentra disponible para apostar."}
        )


def validate_selection_has_odds(evento, seleccion):
    try:
        cuotas = evento.cuotas
    except Cuota.DoesNotExist as exc:
        raise serializers.ValidationError(
            {"seleccion": "El evento no tiene cuotas configuradas."}
        ) from exc

    cuota_actual = get_current_odds(cuotas, seleccion)
    if cuota_actual is None or cuota_actual <= Decimal("0"):
        raise serializers.ValidationError(
            {"seleccion": "La seleccion no es valida dentro de las cuotas del evento."}
        )

    return cuotas, cuota_actual


class ApuestaSerializer(serializers.ModelSerializer):
    stake = serializers.DecimalField(
        source="monto_apostado",
        max_digits=10,
        decimal_places=2,
        write_only=True,
    )
    evento = serializers.PrimaryKeyRelatedField(queryset=Evento.objects.all())
    cuota_fijada = serializers.DecimalField(max_digits=6, decimal_places=2, read_only=True)
    ganancia_potencial = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    evento_detalle = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Apuesta
        fields = (
            "id",
            "evento",
            "evento_detalle",
            "seleccion",
            "stake",
            "monto_apostado",
            "cuota_fijada",
            "estado",
            "ganancia_potencial",
            "fecha_creacion",
        )
        read_only_fields = (
            "id",
            "monto_apostado",
            "cuota_fijada",
            "estado",
            "ganancia_potencial",
            "fecha_creacion",
            "evento_detalle",
        )

    def validate_stake(self, value):
        if value <= Decimal("0"):
            raise serializers.ValidationError(
                "El monto de la apuesta debe ser estrictamente mayor a cero."
            )
        return quantize_bet_amount(value)

    def validate(self, attrs):
        evento = attrs["evento"]
        seleccion = attrs["seleccion"]

        validate_event_accepts_bets(evento)
        _, cuota_actual = validate_selection_has_odds(evento, seleccion)
        attrs["cuota_fijada"] = cuota_actual

        return attrs

    def create(self, validated_data):
        request = self.context.get("request")
        return Apuesta.objects.create(
            usuario=request.user,
            estado=Apuesta.Estado.PENDIENTE,
            **validated_data,
        )

    def get_evento_detalle(self, obj):
        return {
            "id": obj.evento_id,
            "deporte": obj.evento.deporte,
            "equipo_local": obj.evento.equipo_local,
            "equipo_visitante": obj.evento.equipo_visitante,
            "fecha_hora": obj.evento.fecha_hora,
            "estado": obj.evento.estado,
        }


class MisApuestasSerializer(serializers.ModelSerializer):
    evento = serializers.SerializerMethodField()
    monto_apostado = serializers.DecimalField(max_digits=10, decimal_places=2)
    ganancia_potencial = serializers.DecimalField(max_digits=10, decimal_places=2)
    cuota_fijada = serializers.DecimalField(max_digits=6, decimal_places=2)

    class Meta:
        model = Apuesta
        fields = (
            "id",
            "evento",
            "seleccion",
            "estado",
            "monto_apostado",
            "cuota_fijada",
            "ganancia_potencial",
            "fecha_creacion",
        )
        read_only_fields = fields

    def get_evento(self, obj):
        return {
            "id": obj.evento_id,
            "deporte": obj.evento.deporte,
            "partido": f"{obj.evento.equipo_local} vs {obj.evento.equipo_visitante}",
            "fecha_hora": obj.evento.fecha_hora,
        }
