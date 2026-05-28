from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from decimal import Decimal
import uuid

from django.contrib.auth.models import User
from django.db import close_old_connections
from django.db.models import Q, Sum
from django.test import TestCase, TransactionTestCase
from django.urls import reverse
from django.utils import timezone
from hypothesis import given, settings
from hypothesis import strategies as st
from hypothesis.extra.django import TestCase as HypothesisTestCase
from rest_framework.test import APIClient

from apuestas.models import Apuesta
from deportes.models import Cuota, Evento
from finanzas.models import Billetera, LedgerEntry, Perfil


PASSWORD = "ClaveSegura123!"


def money(value, places="0.0001"):
    return Decimal(str(value)).quantize(Decimal(places))


def wallet_balance(wallet):
    totals = LedgerEntry.objects.filter(billetera=wallet).aggregate(
        creditos=Sum("monto", filter=Q(direccion=LedgerEntry.Direccion.CREDIT)),
        debitos=Sum("monto", filter=Q(direccion=LedgerEntry.Direccion.DEBIT)),
    )
    creditos = totals["creditos"] or Decimal("0")
    debitos = totals["debitos"] or Decimal("0")
    return money(creditos - debitos)


def global_ledger_delta():
    totals = LedgerEntry.objects.aggregate(
        creditos=Sum("monto", filter=Q(direccion=LedgerEntry.Direccion.CREDIT)),
        debitos=Sum("monto", filter=Q(direccion=LedgerEntry.Direccion.DEBIT)),
    )
    creditos = totals["creditos"] or Decimal("0")
    debitos = totals["debitos"] or Decimal("0")
    return money(creditos - debitos)


def create_verified_user(username="tester", daily_limit="1000.0000"):
    user = User.objects.create_user(username=username, password=PASSWORD)
    Perfil.objects.create(
        usuario=user,
        dni=str(10000000 + user.id)[-8:],
        fecha_nacimiento=timezone.localdate() - timedelta(days=365 * 25),
        estado=Perfil.Estado.VERIFICADO,
        limite_deposito_diario=money(daily_limit),
    )
    wallet = Billetera.objects.create(usuario=user, tipo=Billetera.TipoCuenta.USUARIO)
    return user, wallet


def get_system_wallet(tipo):
    wallet, _ = Billetera.objects.get_or_create(tipo=tipo, usuario=None)
    return wallet


def fund_user(wallet, amount):
    tx_id = uuid.uuid4()
    house_wallet = get_system_wallet(Billetera.TipoCuenta.CASA)
    amount = money(amount)
    LedgerEntry.objects.create(
        billetera=wallet,
        transaction_id=tx_id,
        direccion=LedgerEntry.Direccion.CREDIT,
        monto=amount,
        descripcion="Fondeo inicial de prueba",
    )
    LedgerEntry.objects.create(
        billetera=house_wallet,
        transaction_id=tx_id,
        direccion=LedgerEntry.Direccion.DEBIT,
        monto=amount,
        descripcion="Contrapartida de fondeo inicial de prueba",
    )


def create_future_event(local="Local FC", visitante="Visitante FC", odds="2.00"):
    evento = Evento.objects.create(
        deporte="FUTBOL",
        equipo_local=local,
        equipo_visitante=visitante,
        fecha_hora=timezone.now() + timedelta(days=1),
        estado="PENDIENTE",
    )
    Cuota.objects.create(
        evento=evento,
        paga_local=Decimal(odds),
        paga_empate=Decimal("3.00"),
        paga_visitante=Decimal("2.80"),
    )
    return evento


class ValidacionesGeneralesReglasNegocioTest(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_registro_json_rechaza_menores_de_edad(self):
        response = self.client.post(
            reverse("finanzas:api_registrar_usuario"),
            {
                "username": "menor",
                "first_name": "Menor",
                "last_name": "Edad",
                "email": "menor@example.com",
                "password": PASSWORD,
                "password_confirm": PASSWORD,
                "dni": "12345678",
                "fecha_nacimiento": timezone.localdate() - timedelta(days=365 * 16),
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("fecha_nacimiento", response.data)

    def test_apuesta_rechaza_balance_insuficiente_por_partida_doble(self):
        user, _wallet = create_verified_user("sin_saldo")
        evento = create_future_event()
        self.client.force_login(user)

        response = self.client.post(
            reverse("apuestas:api_crear_apuesta"),
            {"evento": evento.id, "seleccion": Apuesta.Seleccion.LOCAL, "stake": "20.00"},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["code"], "insufficient_funds")
        self.assertEqual(Apuesta.objects.count(), 0)

    def test_recarga_bloquea_si_supera_limite_deposito_diario(self):
        user, _wallet = create_verified_user("limite_diario", daily_limit="50.0000")
        self.client.force_login(user)

        response = self.client.post(
            reverse("finanzas:api_recargar_saldo"),
            {"metodo": "TARJETA", "monto": "60.0000"},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("limite", str(response.data).lower())
        self.assertEqual(global_ledger_delta(), Decimal("0.0000"))


class ConcurrenciaExtremaCondicionCarreraTest(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        self.user, self.wallet = create_verified_user("concurrente")
        fund_user(self.wallet, "50.0000")
        self.evento = create_future_event()
        self.url = reverse("apuestas:api_crear_apuesta")

    def _post_bet(self):
        close_old_connections()
        client = APIClient()
        client.force_login(self.user)
        response = client.post(
            self.url,
            {
                "evento": self.evento.id,
                "seleccion": Apuesta.Seleccion.LOCAL,
                "stake": "20.00",
            },
            format="json",
        )
        close_old_connections()
        return response.status_code

    def test_cinco_apuestas_simultaneas_solo_dos_consumen_saldo(self):
        with ThreadPoolExecutor(max_workers=5) as executor:
            status_codes = list(executor.map(lambda _index: self._post_bet(), range(5)))

        self.assertEqual(status_codes.count(201), 2)
        self.assertEqual(status_codes.count(400), 3)

        self.wallet.refresh_from_db()
        self.assertEqual(wallet_balance(self.wallet), Decimal("10.0000"))
        self.assertEqual(Apuesta.objects.filter(usuario=self.user).count(), 2)
        self.assertEqual(global_ledger_delta(), Decimal("0.0000"))


class InvariantesFinancierasPropertyBasedTest(HypothesisTestCase):
    @settings(max_examples=25, deadline=None)
    @given(
        operaciones=st.lists(
            st.tuples(
                st.sampled_from(["RECARGA", "RETIRO", "APUESTA"]),
                st.decimals(min_value=Decimal("1.0000"), max_value=Decimal("300.0000"), places=4),
            ),
            min_size=1,
            max_size=12,
        )
    )
    def test_partida_doble_y_blindaje_anti_saldo_negativo(self, operaciones):
        user, wallet = create_verified_user("property_user", daily_limit="100000.0000")
        evento = create_future_event()
        client = APIClient()
        client.force_login(user)

        for operacion, amount in operaciones:
            amount = money(amount)
            if operacion == "RECARGA":
                client.post(
                    reverse("finanzas:api_recargar_saldo"),
                    {"metodo": "TARJETA", "monto": f"{amount:.4f}"},
                    format="json",
                )
            elif operacion == "RETIRO":
                client.post(
                    reverse("finanzas:api_retirar_saldo"),
                    {"metodo": "TRANSFERENCIA", "monto": f"{amount:.4f}"},
                    format="json",
                )
            else:
                client.post(
                    reverse("apuestas:api_crear_apuesta"),
                    {
                        "evento": evento.id,
                        "seleccion": Apuesta.Seleccion.LOCAL,
                        "stake": f"{amount.quantize(Decimal('0.01')):.2f}",
                    },
                    format="json",
                )

        self.assertEqual(global_ledger_delta(), Decimal("0.0000"))
        self.assertGreaterEqual(wallet_balance(wallet), Decimal("0.0000"))

    @settings(max_examples=100, deadline=None)
    @given(
        stake=st.decimals(min_value=Decimal("1.00"), max_value=Decimal("9999.99"), places=2),
        cuota=st.decimals(min_value=Decimal("1.01"), max_value=Decimal("99.99"), places=2),
        saldo_inicial=st.decimals(min_value=Decimal("10000.00"), max_value=Decimal("999999.99"), places=2),
    )
    def test_precision_decimal_del_payout_sin_float(self, stake, cuota, saldo_inicial):
        user, wallet = create_verified_user("precision_user", daily_limit="1000000.0000")
        fund_user(wallet, money(saldo_inicial))
        evento = create_future_event(odds=str(cuota))
        client = APIClient()
        client.force_login(user)

        response = client.post(
            reverse("apuestas:api_crear_apuesta"),
            {"evento": evento.id, "seleccion": Apuesta.Seleccion.LOCAL, "stake": f"{stake:.2f}"},
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        expected_payout = (stake * cuota).quantize(Decimal("0.01"))
        self.assertEqual(Decimal(response.data["ticket"]["ganancia_potencial"]), expected_payout)
