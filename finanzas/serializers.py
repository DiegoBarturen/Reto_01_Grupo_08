from datetime import date, timedelta
from decimal import Decimal
import uuid

from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import Q, Sum
from django.utils import timezone
from rest_framework import serializers

from .models import Billetera, LedgerEntry, Perfil


LEDGER_PRECISION = Decimal("0.0001")
USER_RECHARGE_PREFIX = "Recarga via "
USER_WITHDRAWAL_DESCRIPTION = "Retiro de saldo"


def _calculate_age(fecha_nacimiento):
    """Calcula la edad exacta sin aproximaciones por años bisiestos."""
    hoy = date.today()
    return hoy.year - fecha_nacimiento.year - (
        (hoy.month, hoy.day) < (fecha_nacimiento.month, fecha_nacimiento.day)
    )


def _quantize_financial(value):
    """Fuerza salida 18.4 para mantener consistencia contable."""
    return (value or Decimal("0")).quantize(LEDGER_PRECISION)


def _wallet_balance_for_queryset(billetera):
    """Saldo real = creditos - debitos, calculado solo desde el ledger."""
    totals = billetera.movimientos.aggregate(
        creditos=Sum("monto", filter=Q(direccion=LedgerEntry.Direccion.CREDIT)),
        debitos=Sum("monto", filter=Q(direccion=LedgerEntry.Direccion.DEBIT)),
    )
    creditos = totals["creditos"] or Decimal("0")
    debitos = totals["debitos"] or Decimal("0")
    return _quantize_financial(creditos - debitos)


class UsuarioResumenSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "username", "first_name", "last_name", "email")
        read_only_fields = fields


class UsuarioRegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, style={"input_type": "password"})
    password_confirm = serializers.CharField(write_only=True, style={"input_type": "password"})
    dni = serializers.CharField(write_only=True, max_length=8, min_length=8)
    fecha_nacimiento = serializers.DateField(write_only=True)
    estado = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = User
        fields = (
            "id",
            "username",
            "first_name",
            "last_name",
            "email",
            "password",
            "password_confirm",
            "dni",
            "fecha_nacimiento",
            "estado",
        )
        read_only_fields = ("id", "estado")

    def validate_fecha_nacimiento(self, value):
        if _calculate_age(value) < 18:
            raise serializers.ValidationError(
                "Debes ser mayor de 18 años para registrarte."
            )
        return value

    def validate_dni(self, value):
        if not value.isdigit() or len(value) != 8:
            raise serializers.ValidationError(
                "El DNI peruano debe contener exactamente 8 dígitos numéricos."
            )
        if Perfil.objects.filter(dni=value).exists():
            raise serializers.ValidationError("Ya existe un perfil registrado con este DNI.")
        return value

    def validate(self, attrs):
        if attrs["password"] != attrs["password_confirm"]:
            raise serializers.ValidationError(
                {"password_confirm": "Las contraseñas no coinciden."}
            )
        return attrs

    def get_estado(self, obj):
        perfil = getattr(obj, "perfil", None)
        return perfil.estado if perfil else Perfil.Estado.PENDIENTE

    @transaction.atomic
    def create(self, validated_data):
        dni = validated_data.pop("dni")
        fecha_nacimiento = validated_data.pop("fecha_nacimiento")
        validated_data.pop("password_confirm")
        password = validated_data.pop("password")

        user = User(**validated_data)
        user.set_password(password)
        user.save()

        # El estado inicial queda pendiente hasta revisión KYC posterior.
        Perfil.objects.create(
            usuario=user,
            dni=dni,
            fecha_nacimiento=fecha_nacimiento,
            estado=Perfil.Estado.PENDIENTE,
        )

        Billetera.objects.create(
            usuario=user,
            tipo=Billetera.TipoCuenta.USUARIO,
        )
        return user


class WalletBalanceSerializer(serializers.ModelSerializer):
    usuario = UsuarioResumenSerializer(read_only=True)
    saldo = serializers.SerializerMethodField()

    class Meta:
        model = Billetera
        fields = ("id", "tipo", "usuario", "creado_en", "saldo")
        read_only_fields = fields

    def get_saldo(self, obj):
        return _wallet_balance_for_queryset(obj)


class LedgerEntrySerializer(serializers.ModelSerializer):
    monto = serializers.SerializerMethodField()
    billetera_tipo = serializers.CharField(source="billetera.tipo", read_only=True)

    class Meta:
        model = LedgerEntry
        fields = (
            "id",
            "transaction_id",
            "direccion",
            "monto",
            "descripcion",
            "billetera_tipo",
            "creado_en",
        )
        read_only_fields = fields

    def get_monto(self, obj):
        return f"{_quantize_financial(obj.monto):.4f}"


class TransactionSimulatedSerializer(serializers.Serializer):
    class TipoOperacion(serializers.ChoiceField):
        pass

    OPERACION_RECARGA = "RECARGA"
    OPERACION_RETIRO = "RETIRO"
    OPERACION_CHOICES = (
        (OPERACION_RECARGA, "Recarga"),
        (OPERACION_RETIRO, "Retiro"),
    )
    METODO_CHOICES = (
        ("TARJETA", "Tarjeta"),
        ("TRANSFERENCIA", "Transferencia"),
    )

    operacion = serializers.ChoiceField(choices=OPERACION_CHOICES)
    metodo = serializers.ChoiceField(choices=METODO_CHOICES)
    monto = serializers.DecimalField(max_digits=18, decimal_places=4)

    default_error_messages = {
        "unverified_user": "Solo los usuarios verificados pueden retirar saldo.",
        "insufficient_funds": "Saldo insuficiente para realizar el retiro.",
        "responsible_gaming_limit": "La recarga excede el limite de deposito configurado.",
        "self_excluded": "La cuenta se encuentra autoexcluida temporalmente.",
        "missing_user": "No se pudo identificar al usuario autenticado.",
    }

    def validate_monto(self, value):
        if value <= Decimal("0"):
            raise serializers.ValidationError("El monto debe ser estrictamente mayor a cero.")
        return _quantize_financial(value)

    def validate(self, attrs):
        user = self._get_authenticated_user()
        perfil = self._get_user_profile(user)
        monto = attrs["monto"]

        self._validate_not_self_excluded(perfil)

        if attrs["operacion"] == self.OPERACION_RECARGA:
            self._validate_recharge_limits(user=user, perfil=perfil, monto=monto)
        else:
            self._validate_withdrawal_requirements(user=user, perfil=perfil, monto=monto)

        return attrs

    def _get_authenticated_user(self):
        request = self.context.get("request")
        user = getattr(request, "user", None)
        if not user or not user.is_authenticated:
            self.fail("missing_user")
        return user

    def _get_user_profile(self, user):
        try:
            return user.perfil
        except Perfil.DoesNotExist as exc:
            raise serializers.ValidationError(
                {"perfil": "El usuario no cuenta con un perfil financiero/KYC asociado."}
            ) from exc

    def _validate_not_self_excluded(self, perfil):
        now = timezone.now()
        if perfil.autoexcluido_hasta and perfil.autoexcluido_hasta > now:
            self.fail("self_excluded")

    def _validate_recharge_limits(self, user, perfil, monto):
        for periodo, limite in self._configured_recharge_limits(perfil).items():
            acumulado = self._sum_user_recharges(user=user, periodo=periodo)
            if acumulado + monto > limite:
                raise serializers.ValidationError(
                    {
                        "monto": (
                            f"La recarga excede el limite {periodo.lower()} configurado. "
                            f"Limite: S/ {limite.quantize(LEDGER_PRECISION)} | "
                            f"Acumulado: S/ {acumulado.quantize(LEDGER_PRECISION)}"
                        )
                    }
                )

    def _validate_withdrawal_requirements(self, user, perfil, monto):
        if perfil.estado != Perfil.Estado.VERIFICADO:
            self.fail("unverified_user")

        billetera_usuario, _ = Billetera.objects.get_or_create(
            usuario=user,
            defaults={"tipo": Billetera.TipoCuenta.USUARIO},
        )
        saldo = _wallet_balance_for_queryset(billetera_usuario)
        if saldo < monto:
            self.fail("insufficient_funds")

    def _configured_recharge_limits(self, perfil):
        """Solo valida límites que existan realmente en el modelo."""
        limits = {}
        if getattr(perfil, "limite_deposito_diario", None) is not None:
            limits["DIARIO"] = perfil.limite_deposito_diario
        if getattr(perfil, "limite_deposito_semanal", None) is not None:
            limits["SEMANAL"] = perfil.limite_deposito_semanal
        if getattr(perfil, "limite_deposito_mensual", None) is not None:
            limits["MENSUAL"] = perfil.limite_deposito_mensual
        return limits

    def _sum_user_recharges(self, user, periodo):
        """
        Solo suma recargas reales del usuario.
        Excluye premios, devoluciones y otros creditos porque filtramos por
        descripcion contable estandarizada del flujo de recarga.
        """
        now = timezone.now()
        queryset = LedgerEntry.objects.filter(
            billetera__usuario=user,
            direccion=LedgerEntry.Direccion.CREDIT,
            descripcion__startswith=USER_RECHARGE_PREFIX,
        )

        if periodo == "DIARIO":
            queryset = queryset.filter(creado_en__date=now.date())
        elif periodo == "SEMANAL":
            start_of_week = now.date() - timedelta(days=now.weekday())
            queryset = queryset.filter(creado_en__date__gte=start_of_week)
        elif periodo == "MENSUAL":
            queryset = queryset.filter(creado_en__year=now.year, creado_en__month=now.month)

        total = queryset.aggregate(total=Sum("monto"))["total"] or Decimal("0")
        return _quantize_financial(total)

    @transaction.atomic
    def create(self, validated_data):
        user = self._get_authenticated_user()
        billetera_usuario, _ = Billetera.objects.select_for_update().get_or_create(
            usuario=user,
            defaults={"tipo": Billetera.TipoCuenta.USUARIO},
        )
        billetera_casa, _ = Billetera.objects.select_for_update().get_or_create(
            tipo=Billetera.TipoCuenta.CASA,
            defaults={"usuario": None},
        )

        monto = validated_data["monto"]
        metodo = validated_data["metodo"]
        operacion = validated_data["operacion"]
        tx_id = uuid.uuid4()

        if operacion == self.OPERACION_RECARGA:
            descripcion_usuario = f"{USER_RECHARGE_PREFIX}{metodo}"
            descripcion_casa = f"Ingreso de recarga de {user.username}"

            LedgerEntry.objects.create(
                billetera=billetera_usuario,
                transaction_id=tx_id,
                direccion=LedgerEntry.Direccion.CREDIT,
                monto=monto,
                descripcion=descripcion_usuario,
            )
            LedgerEntry.objects.create(
                billetera=billetera_casa,
                transaction_id=tx_id,
                direccion=LedgerEntry.Direccion.DEBIT,
                monto=monto,
                descripcion=descripcion_casa,
            )
        else:
            # Revalidamos saldo dentro de la transaccion para cerrar carrera de concurrencia.
            saldo_actual = _wallet_balance_for_queryset(billetera_usuario)
            if saldo_actual < monto:
                self.fail("insufficient_funds")

            LedgerEntry.objects.create(
                billetera=billetera_usuario,
                transaction_id=tx_id,
                direccion=LedgerEntry.Direccion.DEBIT,
                monto=monto,
                descripcion=USER_WITHDRAWAL_DESCRIPTION,
            )
            LedgerEntry.objects.create(
                billetera=billetera_casa,
                transaction_id=tx_id,
                direccion=LedgerEntry.Direccion.CREDIT,
                monto=monto,
                descripcion=f"Egreso por retiro de {user.username}",
            )

        return {
            "transaction_id": tx_id,
            "operacion": operacion,
            "metodo": metodo,
            "monto": monto,
            "saldo_resultante": _wallet_balance_for_queryset(billetera_usuario),
        }

    def to_representation(self, instance):
        return {
            "transaction_id": str(instance["transaction_id"]),
            "operacion": instance["operacion"],
            "metodo": instance["metodo"],
            "monto": f'{instance["monto"]:.4f}',
            "saldo_resultante": f'{instance["saldo_resultante"]:.4f}',
        }
