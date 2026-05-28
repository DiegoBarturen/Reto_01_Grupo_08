from decimal import Decimal
import uuid

from django.db import transaction
from django.db.models import Q, Sum
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from deportes.models import Cuota, Evento
from finanzas.models import Billetera, LedgerEntry, Perfil

from .models import Apuesta
from .serializers import (
    ApuestaSerializer,
    BETTING_PRECISION,
    MisApuestasSerializer,
    get_current_odds,
    validate_event_accepts_bets,
)


class FinancialAPIError(Exception):
    status_code = status.HTTP_400_BAD_REQUEST
    code = "financial_error"
    detail = "No se pudo completar la operacion financiera."

    def __init__(self, detail=None, *, extra=None):
        self.detail = detail or self.detail
        self.extra = extra or {}
        super().__init__(self.detail)

    def as_response(self):
        payload = {"detail": self.detail, "code": self.code}
        payload.update(self.extra)
        return Response(payload, status=self.status_code)


class PerfilFinancieroInvalido(FinancialAPIError):
    code = "invalid_financial_profile"
    detail = "El usuario no cuenta con un perfil financiero valido."


class PerfilNoVerificado(FinancialAPIError):
    code = "profile_not_verified"
    detail = "Solo los usuarios con perfil VERIFICADO pueden realizar apuestas."


class SaldoInsuficiente(FinancialAPIError):
    code = "insufficient_funds"
    detail = "Saldo insuficiente para realizar la apuesta."


class EventoNoDisponible(FinancialAPIError):
    code = "event_not_available"
    detail = "El evento deportivo no acepta apuestas en este momento."


class CuotaInvalida(FinancialAPIError):
    code = "invalid_odds"
    detail = "La seleccion no tiene una cuota valida para este evento."


def _format_money(value, precision=BETTING_PRECISION):
    amount = (value or Decimal("0")).quantize(precision)
    return f"{amount:.{abs(precision.as_tuple().exponent)}f}"


def _calculate_wallet_balance(wallet):
    totals = LedgerEntry.objects.filter(billetera=wallet).aggregate(
        creditos=Sum("monto", filter=Q(direccion=LedgerEntry.Direccion.CREDIT)),
        debitos=Sum("monto", filter=Q(direccion=LedgerEntry.Direccion.DEBIT)),
    )
    creditos = totals["creditos"] or Decimal("0")
    debitos = totals["debitos"] or Decimal("0")
    return (creditos - debitos).quantize(Decimal("0.0001"))


def _get_locked_user_wallet(user):
    wallet, _ = Billetera.objects.select_for_update().get_or_create(
        usuario=user,
        defaults={"tipo": Billetera.TipoCuenta.USUARIO},
    )
    return wallet


def _get_locked_system_wallet(tipo):
    wallet = Billetera.objects.select_for_update().filter(tipo=tipo, usuario__isnull=True).first()
    if wallet:
        return wallet
    return Billetera.objects.create(tipo=tipo, usuario=None)


def _get_locked_verified_profile(user):
    try:
        perfil = Perfil.objects.select_for_update().get(usuario=user)
    except Perfil.DoesNotExist as exc:
        raise PerfilFinancieroInvalido() from exc

    if perfil.estado != Perfil.Estado.VERIFICADO:
        raise PerfilNoVerificado(extra={"estado_actual": perfil.estado})

    return perfil


def _get_locked_event_and_odds(evento_id, seleccion):
    try:
        evento = Evento.objects.select_for_update().get(pk=evento_id)
    except Evento.DoesNotExist as exc:
        raise EventoNoDisponible("El evento deportivo solicitado no existe.") from exc

    try:
        validate_event_accepts_bets(evento)
    except ValidationError as exc:
        raise EventoNoDisponible() from exc

    try:
        cuotas = Cuota.objects.select_for_update().get(evento=evento)
    except Cuota.DoesNotExist as exc:
        raise CuotaInvalida("El evento no tiene cuotas configuradas.") from exc

    cuota_actual = get_current_odds(cuotas, seleccion)
    if cuota_actual is None or cuota_actual <= Decimal("0"):
        raise CuotaInvalida()

    return evento, cuota_actual


def _create_bet_ledger_pair(*, user_wallet, escrow_wallet, amount, user, apuesta):
    transaction_id = uuid.uuid4()
    LedgerEntry.objects.create(
        billetera=user_wallet,
        transaction_id=transaction_id,
        direccion=LedgerEntry.Direccion.DEBIT,
        monto=amount,
        descripcion=f"Apuesta #{apuesta.id} - {apuesta.evento.equipo_local} vs {apuesta.evento.equipo_visitante}",
    )
    LedgerEntry.objects.create(
        billetera=escrow_wallet,
        transaction_id=transaction_id,
        direccion=LedgerEntry.Direccion.CREDIT,
        monto=amount,
        descripcion=f"Custodia de apuesta #{apuesta.id} de {user.username}",
    )
    return transaction_id


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def api_crear_apuesta(request):
    serializer = ApuestaSerializer(data=request.data, context={"request": request})
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    try:
        with transaction.atomic():
            _get_locked_verified_profile(request.user)
            user_wallet = _get_locked_user_wallet(request.user)
            escrow_wallet = _get_locked_system_wallet(Billetera.TipoCuenta.PENDIENTES)

            evento, cuota_actual = _get_locked_event_and_odds(
                serializer.validated_data["evento"].id,
                serializer.validated_data["seleccion"],
            )
            stake = serializer.validated_data["monto_apostado"]

            saldo_actual = _calculate_wallet_balance(user_wallet)
            if saldo_actual < stake:
                raise SaldoInsuficiente(
                    extra={
                        "saldo_actual": _format_money(saldo_actual),
                        "monto_solicitado": _format_money(stake),
                    }
                )

            apuesta = Apuesta.objects.create(
                usuario=request.user,
                evento=evento,
                seleccion=serializer.validated_data["seleccion"],
                monto_apostado=stake,
                cuota_fijada=cuota_actual,
                estado=Apuesta.Estado.PENDIENTE,
            )
            transaction_id = _create_bet_ledger_pair(
                user_wallet=user_wallet,
                escrow_wallet=escrow_wallet,
                amount=stake,
                user=request.user,
                apuesta=apuesta,
            )
            saldo_resultante = _calculate_wallet_balance(user_wallet)
    except FinancialAPIError as exc:
        return exc.as_response()

    return Response(
        {
            "transaction_id": str(transaction_id),
            "saldo_resultante": _format_money(saldo_resultante),
            "ticket": ApuestaSerializer(apuesta).data,
        },
        status=status.HTTP_201_CREATED,
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def api_listar_mis_apuestas(request):
    apuestas = (
        Apuesta.objects.filter(usuario=request.user)
        .select_related("evento")
        .order_by("-fecha_creacion")
    )
    serializer = MisApuestasSerializer(apuestas, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)
