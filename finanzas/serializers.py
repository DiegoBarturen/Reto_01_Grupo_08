from rest_framework import serializers

from .models import Billetera, Transaccion


class TransaccionSerializer(serializers.ModelSerializer):
    tipo_display = serializers.CharField(source="get_tipo_display", read_only=True)
    metodo_display = serializers.CharField(source="get_metodo_display", read_only=True)

    class Meta:
        model = Transaccion
        fields = (
            "id",
            "tipo",
            "tipo_display",
            "metodo",
            "metodo_display",
            "monto",
            "descripcion",
            "creado_en",
        )


class BilleteraSerializer(serializers.ModelSerializer):
    usuario = serializers.SerializerMethodField()
    total_movimientos = serializers.SerializerMethodField()

    class Meta:
        model = Billetera
        fields = (
            "id",
            "saldo",
            "actualizado_en",
            "creado_en",
            "usuario",
            "total_movimientos",
        )

    def get_usuario(self, obj):
        return {
            "username": obj.usuario.username,
            "first_name": obj.usuario.first_name,
            "last_name": obj.usuario.last_name,
            "email": obj.usuario.email,
        }

    def get_total_movimientos(self, obj):
        return obj.transacciones.count()


class RecargaSerializer(serializers.Serializer):
    metodo = serializers.ChoiceField(choices=Transaccion.Metodo.choices)
    monto = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=1)


class RetiroSerializer(serializers.Serializer):
    metodo = serializers.ChoiceField(choices=Transaccion.Metodo.choices)
    monto = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=50)
