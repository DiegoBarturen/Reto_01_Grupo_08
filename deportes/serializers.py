from decimal import Decimal
from django.utils import timezone
from rest_framework import serializers
from .models import Cuota, Evento


ODDS_PRECISION = Decimal("0.01")
MIN_ODDS = Decimal("1.00")


def quantize_odds(value):
    return value.quantize(ODDS_PRECISION)


class CuotaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Cuota
        fields = ("paga_local", "paga_empate", "paga_visitante")

    def validate(self, attrs):
        for field in ("paga_local", "paga_empate", "paga_visitante"):
            value = attrs.get(field)
            if value is None:
                continue
            if value < MIN_ODDS:
                raise serializers.ValidationError(
                    {field: "La cuota debe ser mayor o igual a 1.00."}
                )
            attrs[field] = quantize_odds(value)
        return attrs


class EventoSerializer(serializers.ModelSerializer):
    cuotas = serializers.SerializerMethodField()
    deporte_display = serializers.CharField(source="get_deporte_display", read_only=True)
    estado_display = serializers.CharField(source="get_estado_display", read_only=True)
    acepta_apuestas = serializers.SerializerMethodField()

    class Meta:
        model = Evento
        fields = (
            "id",
            "deporte",
            "deporte_display",
            "equipo_local",
            "equipo_visitante",
            "fecha_hora",
            "estado",
            "estado_display",
            "acepta_apuestas",
            "cuotas",
        )
        read_only_fields = ("id", "deporte_display", "estado_display", "acepta_apuestas")

    def to_internal_value(self, data):
        mutable_data = data.copy()
        self._cuotas_input = mutable_data.pop("cuotas", None)
        return super().to_internal_value(mutable_data)

    def validate_fecha_hora(self, value):
        if self.instance is None and value <= timezone.now():
            raise serializers.ValidationError(
                "La fecha y hora del evento debe ser futura al crear un evento apostable."
            )
        return value

    def validate(self, attrs):
        cuotas_data = getattr(self, "_cuotas_input", None)
        if cuotas_data is not None:
            cuotas_serializer = CuotaSerializer(data=cuotas_data, partial=self.partial)
            cuotas_serializer.is_valid(raise_exception=True)
            attrs["cuotas_data"] = cuotas_serializer.validated_data

        equipo_local = attrs.get("equipo_local", getattr(self.instance, "equipo_local", ""))
        equipo_visitante = attrs.get(
            "equipo_visitante", getattr(self.instance, "equipo_visitante", "")
        )

        if equipo_local and equipo_visitante and equipo_local.strip().lower() == equipo_visitante.strip().lower():
            raise serializers.ValidationError(
                {"equipo_visitante": "El equipo visitante debe ser distinto al equipo local."}
            )

        return attrs

    def create(self, validated_data):
        cuotas_data = validated_data.pop("cuotas_data", None)
        evento = Evento.objects.create(**validated_data)
        if cuotas_data:
            Cuota.objects.create(evento=evento, **cuotas_data)
        return evento

    def update(self, instance, validated_data):
        cuotas_data = validated_data.pop("cuotas_data", None)

        for field, value in validated_data.items():
            setattr(instance, field, value)
        instance.save()

        if cuotas_data is not None:
            Cuota.objects.update_or_create(evento=instance, defaults=cuotas_data)

        return instance

    def get_cuotas(self, obj):
        try:
            return CuotaSerializer(obj.cuotas).data
        except Cuota.DoesNotExist:
            return None

    def get_acepta_apuestas(self, obj):
        return obj.estado == "PENDIENTE" and obj.fecha_hora > timezone.now() and hasattr(obj, "cuotas")


class EventoCarteleraSerializer(EventoSerializer):
    class Meta(EventoSerializer.Meta):
        read_only_fields = EventoSerializer.Meta.fields
