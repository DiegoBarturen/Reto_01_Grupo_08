from django.db import transaction

from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Billetera, Transaccion
from .serializers import BilleteraSerializer, RecargaSerializer, RetiroSerializer, TransaccionSerializer
from .views import crear_auditoria


class BilleteraAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        billetera, _ = Billetera.objects.get_or_create(usuario=request.user)
        serializer = BilleteraSerializer(billetera)
        return Response(serializer.data)


class TransaccionListAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        billetera, _ = Billetera.objects.get_or_create(usuario=request.user)
        transacciones = billetera.transacciones.all()
        serializer = TransaccionSerializer(transacciones, many=True)
        return Response(serializer.data)


class RecargaAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        serializer = RecargaSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        billetera = Billetera.objects.select_for_update().get(usuario=request.user)
        monto = serializer.validated_data["monto"]
        metodo = serializer.validated_data["metodo"]
        metodo_label = Transaccion.Metodo(metodo).label

        billetera.saldo += monto
        billetera.save(update_fields=["saldo", "actualizado_en"])

        transaccion = Transaccion.objects.create(
            billetera=billetera,
            tipo=Transaccion.Tipo.RECARGA,
            metodo=metodo,
            monto=monto,
            descripcion=f"Recarga de saldo por S/ {monto} mediante {metodo_label.lower()}.",
        )
        crear_auditoria(
            request.user,
            "RECARGA_SALDO_API",
            f"El usuario recargo S/ {monto} mediante {metodo_label.lower()} desde API. Nuevo saldo: S/ {billetera.saldo}.",
        )

        return Response(
            {
                "mensaje": "Recarga registrada correctamente.",
                "saldo_actual": billetera.saldo,
                "transaccion": TransaccionSerializer(transaccion).data,
            },
            status=status.HTTP_201_CREATED,
        )


class RetiroAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        serializer = RetiroSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        billetera = Billetera.objects.select_for_update().get(usuario=request.user)
        monto = serializer.validated_data["monto"]
        metodo = serializer.validated_data["metodo"]

        if billetera.saldo < monto:
            return Response(
                {
                    "detalle": "No cuentas con saldo suficiente para realizar este retiro.",
                    "saldo_actual": billetera.saldo,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        metodo_label = Transaccion.Metodo(metodo).label
        billetera.saldo -= monto
        billetera.save(update_fields=["saldo", "actualizado_en"])

        transaccion = Transaccion.objects.create(
            billetera=billetera,
            tipo=Transaccion.Tipo.RETIRO,
            metodo=metodo,
            monto=monto,
            descripcion=f"Retiro de saldo por S/ {monto} mediante {metodo_label.lower()}.",
        )
        crear_auditoria(
            request.user,
            "RETIRO_SALDO_API",
            f"El usuario retiro S/ {monto} mediante {metodo_label.lower()} desde API. Nuevo saldo: S/ {billetera.saldo}.",
        )

        return Response(
            {
                "mensaje": "Retiro registrado correctamente.",
                "saldo_actual": billetera.saldo,
                "transaccion": TransaccionSerializer(transaccion).data,
            },
            status=status.HTTP_201_CREATED,
        )
