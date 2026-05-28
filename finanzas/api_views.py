from decimal import Decimal
import uuid
from django.db import transaction
from django.db.models import Q, Sum
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from .models import Billetera, LedgerEntry, Perfil
from .serializers import (
    LEDGER_PRECISION,
    LedgerEntrySerializer,
    USER_RECHARGE_PREFIX,
    USER_WITHDRAWAL_DESCRIPTION,
    TransactionSimulatedSerializer,
    UsuarioRegisterSerializer,
)


def _format_money(value):
    amount = (value or Decimal("0")).quantize(LEDGER_PRECISION)
    return f"{amount:.4f}"


def _calculate_wallet_balance(wallet):
    totals = LedgerEntry.objects.filter(billetera=wallet).aggregate(
        creditos=Sum("monto", filter=Q(direccion=LedgerEntry.Direccion.CREDIT)),
        debitos=Sum("monto", filter=Q(direccion=LedgerEntry.Direccion.DEBIT)),
    )
    creditos = totals["creditos"] or Decimal("0")
    debitos = totals["debitos"] or Decimal("0")
    return (creditos - debitos).quantize(LEDGER_PRECISION)


def _get_locked_user_wallet(user):
    wallet, _ = Billetera.objects.select_for_update().get_or_create(
        usuario=user,
        defaults={"tipo": Billetera.TipoCuenta.USUARIO},
    )
    return wallet


def _get_locked_house_wallet():
    wallet, _ = Billetera.objects.select_for_update().get_or_create(
        tipo=Billetera.TipoCuenta.CASA,
        defaults={"usuario": None},
    )
    return wallet


def _sum_user_recharges_today(user):
    return (
        LedgerEntry.objects.filter(
            billetera__usuario=user,
            direccion=LedgerEntry.Direccion.CREDIT,
            descripcion__startswith=USER_RECHARGE_PREFIX,
            creado_en__date=timezone.localdate(),
        ).aggregate(total=Sum("monto"))["total"]
        or Decimal("0")
    ).quantize(LEDGER_PRECISION)


def _create_ledger_pair(*, user_wallet, house_wallet, amount, user_direction, house_direction, user_description, house_description):
    transaction_id = uuid.uuid4()
    LedgerEntry.objects.create(
        billetera=user_wallet,
        transaction_id=transaction_id,
        direccion=user_direction,
        monto=amount,
        descripcion=user_description,
    )
    LedgerEntry.objects.create(
        billetera=house_wallet,
        transaction_id=transaction_id,
        direccion=house_direction,
        monto=amount,
        descripcion=house_description,
    )
    return transaction_id


@api_view(["POST"])
@permission_classes([AllowAny])
def api_registrar_usuario(request):
    serializer = UsuarioRegisterSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    with transaction.atomic():
        user = serializer.save()

        perfil = Perfil.objects.select_for_update().get(usuario=user)
        if perfil.estado != Perfil.Estado.PENDIENTE:
            perfil.estado = Perfil.Estado.PENDIENTE
            perfil.save(update_fields=["estado"])

        billetera, _ = Billetera.objects.select_for_update().get_or_create(
            usuario=user,
            defaults={"tipo": Billetera.TipoCuenta.USUARIO},
        )

    return Response(
        {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "perfil_estado": perfil.estado,
            "billetera_id": billetera.id,
            "billetera_tipo": billetera.tipo,
        },
        status=status.HTTP_201_CREATED,
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def api_consultar_saldo(request):
    billetera, _ = Billetera.objects.get_or_create(
        usuario=request.user,
        defaults={"tipo": Billetera.TipoCuenta.USUARIO},
    )
    saldo = _calculate_wallet_balance(billetera)

    return Response(
        {
            "billetera_id": billetera.id,
            "usuario_id": request.user.id,
            "saldo": _format_money(saldo),
            "precision": "18.4",
        },
        status=status.HTTP_200_OK,
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def api_listar_movimientos_billetera(request):
    billetera, _ = Billetera.objects.get_or_create(
        usuario=request.user,
        defaults={"tipo": Billetera.TipoCuenta.USUARIO},
    )
    movimientos = (
        LedgerEntry.objects.filter(billetera=billetera)
        .select_related("billetera")
        .order_by("-creado_en", "-id")
    )
    serializer = LedgerEntrySerializer(movimientos, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def api_recargar_saldo(request):
    payload = request.data.copy()
    payload["operacion"] = TransactionSimulatedSerializer.OPERACION_RECARGA

    serializer = TransactionSimulatedSerializer(data=payload, context={"request": request})
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    amount = serializer.validated_data["monto"]
    metodo = serializer.validated_data["metodo"]

    with transaction.atomic():
        perfil = Perfil.objects.select_for_update().get(usuario=request.user)
        user_wallet = _get_locked_user_wallet(request.user)
        house_wallet = _get_locked_house_wallet()

        if perfil.autoexcluido_hasta and perfil.autoexcluido_hasta > timezone.now():
            return Response(
                {"detail": "La cuenta se encuentra autoexcluida temporalmente."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        total_hoy = _sum_user_recharges_today(request.user)
        if total_hoy + amount > perfil.limite_deposito_diario:
            return Response(
                {
                    "detail": "La recarga excede el limite diario de deposito.",
                    "limite_diario": _format_money(perfil.limite_deposito_diario),
                    "depositado_hoy": _format_money(total_hoy),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        transaction_id = _create_ledger_pair(
            user_wallet=user_wallet,
            house_wallet=house_wallet,
            amount=amount,
            user_direction=LedgerEntry.Direccion.CREDIT,
            house_direction=LedgerEntry.Direccion.DEBIT,
            user_description=f"{USER_RECHARGE_PREFIX}{metodo}",
            house_description=f"Ingreso de recarga de {request.user.username}",
        )
        saldo_resultante = _calculate_wallet_balance(user_wallet)

    return Response(
        {
            "transaction_id": str(transaction_id),
            "operacion": TransactionSimulatedSerializer.OPERACION_RECARGA,
            "monto": _format_money(amount),
            "saldo_resultante": _format_money(saldo_resultante),
        },
        status=status.HTTP_201_CREATED,
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def api_retirar_saldo(request):
    payload = request.data.copy()
    payload["operacion"] = TransactionSimulatedSerializer.OPERACION_RETIRO

    serializer = TransactionSimulatedSerializer(data=payload, context={"request": request})
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    amount = serializer.validated_data["monto"]
    metodo = serializer.validated_data["metodo"]

    with transaction.atomic():
        perfil = Perfil.objects.select_for_update().get(usuario=request.user)
        user_wallet = _get_locked_user_wallet(request.user)
        house_wallet = _get_locked_house_wallet()

        if perfil.estado != Perfil.Estado.VERIFICADO:
            return Response(
                {"detail": "Solo los usuarios verificados pueden retirar saldo."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        saldo_actual = _calculate_wallet_balance(user_wallet)
        if saldo_actual < amount:
            return Response(
                {
                    "detail": "Saldo insuficiente para realizar el retiro.",
                    "saldo_actual": _format_money(saldo_actual),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        transaction_id = _create_ledger_pair(
            user_wallet=user_wallet,
            house_wallet=house_wallet,
            amount=amount,
            user_direction=LedgerEntry.Direccion.DEBIT,
            house_direction=LedgerEntry.Direccion.CREDIT,
            user_description=USER_WITHDRAWAL_DESCRIPTION,
            house_description=f"Egreso por retiro de {request.user.username} via {metodo}",
        )
        saldo_resultante = _calculate_wallet_balance(user_wallet)

    return Response(
        {
            "transaction_id": str(transaction_id),
            "operacion": TransactionSimulatedSerializer.OPERACION_RETIRO,
            "monto": _format_money(amount),
            "saldo_resultante": _format_money(saldo_resultante),
        },
        status=status.HTTP_200_OK,
    )
