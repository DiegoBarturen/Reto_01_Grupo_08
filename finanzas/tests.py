from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from .models import Auditoria, Billetera, Transaccion


class FinanzasViewsTest(TestCase):
    def test_registro_crea_usuario_billetera_y_auditoria(self):
        response = self.client.post(
            reverse("finanzas:registro"),
            {
                "username": "tomi",
                "first_name": "Tomas",
                "last_name": "Perez",
                "email": "tomi@example.com",
                "password1": "ClaveSegura123!",
                "password2": "ClaveSegura123!",
            },
        )

        self.assertRedirects(response, reverse("finanzas:billetera"))
        usuario = User.objects.get(username="tomi")
        self.assertTrue(Billetera.objects.filter(usuario=usuario).exists())
        self.assertTrue(Auditoria.objects.filter(usuario=usuario, accion="REGISTRO_USUARIO").exists())

    def test_usuario_puede_recargar_saldo(self):
        usuario = User.objects.create_user(username="ana", password="ClaveSegura123!")
        billetera = Billetera.objects.create(usuario=usuario)
        self.client.login(username="ana", password="ClaveSegura123!")

        response = self.client.post(
            reverse("finanzas:recargar_saldo"),
            {"monto": "50.00", "metodo": "YAPE_PLIN"},
        )

        transaccion = Transaccion.objects.get(billetera=billetera)
        self.assertRedirects(response, reverse("finanzas:detalle_transaccion", args=[transaccion.id]))
        billetera.refresh_from_db()
        self.assertEqual(billetera.saldo, Decimal("50.00"))
        self.assertTrue(
            Transaccion.objects.filter(
                billetera=billetera,
                tipo=Transaccion.Tipo.RECARGA,
                metodo=Transaccion.Metodo.YAPE_PLIN,
                monto=Decimal("50.00"),
            ).exists()
        )
        self.assertTrue(Auditoria.objects.filter(usuario=usuario, accion="RECARGA_SALDO").exists())

    def test_usuario_puede_retirar_saldo_si_tiene_saldo_suficiente(self):
        usuario = User.objects.create_user(username="pedro", password="ClaveSegura123!")
        billetera = Billetera.objects.create(usuario=usuario, saldo=Decimal("180.00"))
        self.client.login(username="pedro", password="ClaveSegura123!")

        response = self.client.post(
            reverse("finanzas:retirar_saldo"),
            {"monto": "50.00", "metodo": "TRANSFERENCIA"},
        )

        transaccion = Transaccion.objects.get(billetera=billetera, tipo=Transaccion.Tipo.RETIRO)
        self.assertRedirects(response, reverse("finanzas:detalle_transaccion", args=[transaccion.id]))
        billetera.refresh_from_db()
        self.assertEqual(billetera.saldo, Decimal("130.00"))
        self.assertTrue(
            Transaccion.objects.filter(
                billetera=billetera,
                tipo=Transaccion.Tipo.RETIRO,
                metodo=Transaccion.Metodo.TRANSFERENCIA,
                monto=Decimal("50.00"),
            ).exists()
        )
        self.assertTrue(Auditoria.objects.filter(usuario=usuario, accion="RETIRO_SALDO").exists())

    def test_usuario_no_puede_retirar_mas_saldo_del_disponible(self):
        usuario = User.objects.create_user(username="ines", password="ClaveSegura123!")
        billetera = Billetera.objects.create(usuario=usuario, saldo=Decimal("60.00"))
        self.client.login(username="ines", password="ClaveSegura123!")

        response = self.client.post(
            reverse("finanzas:retirar_saldo"),
            {"monto": "100.00", "metodo": "TARJETA"},
        )

        self.assertEqual(response.status_code, 400)
        self.assertContains(response, "No cuentas con saldo suficiente para realizar este retiro.")
        billetera.refresh_from_db()
        self.assertEqual(billetera.saldo, Decimal("60.00"))

    def test_usuario_no_puede_retirar_menos_del_minimo(self):
        usuario = User.objects.create_user(username="nora", password="ClaveSegura123!")
        billetera = Billetera.objects.create(usuario=usuario, saldo=Decimal("200.00"))
        self.client.login(username="nora", password="ClaveSegura123!")

        response = self.client.post(
            reverse("finanzas:retirar_saldo"),
            {"monto": "30.00", "metodo": "YAPE_PLIN"},
        )

        self.assertEqual(response.status_code, 400)
        self.assertContains(response, "Ensure this value is greater than or equal to 50.00.")
        billetera.refresh_from_db()
        self.assertEqual(billetera.saldo, Decimal("200.00"))

    def test_billetera_muestra_historial_y_enlace_a_detalle(self):
        usuario = User.objects.create_user(username="luis", password="ClaveSegura123!")
        billetera = Billetera.objects.create(usuario=usuario, saldo=Decimal("80.00"))
        transaccion = Transaccion.objects.create(
            billetera=billetera,
            tipo=Transaccion.Tipo.RECARGA,
            metodo=Transaccion.Metodo.TARJETA,
            monto=Decimal("80.00"),
            descripcion="Recarga inicial.",
        )
        self.client.login(username="luis", password="ClaveSegura123!")

        response = self.client.get(reverse("finanzas:billetera"))

        self.assertContains(response, "Ir a recargar saldo")
        self.assertContains(response, reverse("finanzas:detalle_transaccion", args=[transaccion.id]))

    def test_detalle_transaccion_muestra_datos_del_deposito(self):
        usuario = User.objects.create_user(username="maria", password="ClaveSegura123!")
        billetera = Billetera.objects.create(usuario=usuario, saldo=Decimal("50.00"))
        transaccion = Transaccion.objects.create(
            billetera=billetera,
            tipo=Transaccion.Tipo.RECARGA,
            metodo=Transaccion.Metodo.YAPE_PLIN,
            monto=Decimal("50.00"),
            descripcion="Recarga de saldo por S/ 50.00 mediante yape o plin simulado.",
        )
        self.client.login(username="maria", password="ClaveSegura123!")

        response = self.client.get(reverse("finanzas:detalle_transaccion", args=[transaccion.id]))

        self.assertContains(response, "Yape o Plin simulado")
        self.assertContains(response, "S/ 50.00")
        self.assertContains(response, "Recarga de saldo por S/ 50.00 mediante yape o plin simulado.")

    def test_usuario_puede_actualizar_su_perfil(self):
        usuario = User.objects.create_user(
            username="carlos",
            password="ClaveSegura123!",
            first_name="Carlos",
            last_name="Diaz",
            email="carlos@example.com",
        )
        Billetera.objects.create(usuario=usuario)
        self.client.login(username="carlos", password="ClaveSegura123!")

        response = self.client.post(
            reverse("finanzas:perfil"),
            {
                "form_type": "perfil",
                "username": "carlosdev",
                "first_name": "Carlos Andres",
                "last_name": "Diaz",
                "email": "carlosdev@example.com",
            },
        )

        self.assertRedirects(response, reverse("finanzas:perfil"))
        usuario.refresh_from_db()
        self.assertEqual(usuario.username, "carlosdev")
        self.assertEqual(usuario.first_name, "Carlos Andres")
        self.assertEqual(usuario.email, "carlosdev@example.com")
        self.assertTrue(Auditoria.objects.filter(usuario=usuario, accion="ACTUALIZACION_PERFIL").exists())

    def test_usuario_puede_cambiar_su_contrasena(self):
        usuario = User.objects.create_user(username="sofia", password="ClaveSegura123!")
        Billetera.objects.create(usuario=usuario)
        self.client.login(username="sofia", password="ClaveSegura123!")

        response = self.client.post(
            reverse("finanzas:perfil"),
            {
                "form_type": "password",
                "old_password": "ClaveSegura123!",
                "new_password1": "NuevaClaveSegura456!",
                "new_password2": "NuevaClaveSegura456!",
            },
        )

        self.assertRedirects(response, reverse("finanzas:perfil"))
        usuario.refresh_from_db()
        self.assertTrue(usuario.check_password("NuevaClaveSegura456!"))
        self.assertTrue(Auditoria.objects.filter(usuario=usuario, accion="CAMBIO_CONTRASENA").exists())


class FinanzasAPITest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="apiuser",
            password="ClaveSegura123!",
            first_name="Api",
            last_name="Tester",
            email="api@example.com",
        )
        self.billetera = Billetera.objects.create(usuario=self.user, saldo=Decimal("75.00"))
        self.client = APIClient()
        self.client.login(username="apiuser", password="ClaveSegura123!")

    def test_api_billetera_devuelve_datos_principales(self):
        response = self.client.get(reverse("finanzas:api_billetera"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["saldo"], "75.00")
        self.assertEqual(response.data["usuario"]["username"], "apiuser")

    def test_api_transacciones_devuelve_historial(self):
        Transaccion.objects.create(
            billetera=self.billetera,
            tipo=Transaccion.Tipo.RECARGA,
            metodo=Transaccion.Metodo.TARJETA,
            monto=Decimal("25.00"),
            descripcion="Recarga inicial desde API test.",
        )

        response = self.client.get(reverse("finanzas:api_transacciones"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["metodo"], Transaccion.Metodo.TARJETA)

    def test_api_recargas_crea_movimiento_y_actualiza_saldo(self):
        response = self.client.post(
            reverse("finanzas:api_recargas"),
            {
                "metodo": Transaccion.Metodo.YAPE_PLIN,
                "monto": "50.00",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.billetera.refresh_from_db()
        self.assertEqual(self.billetera.saldo, Decimal("125.00"))
        self.assertTrue(
            Transaccion.objects.filter(
                billetera=self.billetera,
                metodo=Transaccion.Metodo.YAPE_PLIN,
                monto=Decimal("50.00"),
            ).exists()
        )
        self.assertTrue(Auditoria.objects.filter(usuario=self.user, accion="RECARGA_SALDO_API").exists())

    def test_api_retiros_crea_movimiento_y_actualiza_saldo(self):
        response = self.client.post(
            reverse("finanzas:api_retiros"),
            {
                "metodo": Transaccion.Metodo.TRANSFERENCIA,
                "monto": "50.00",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.billetera.refresh_from_db()
        self.assertEqual(self.billetera.saldo, Decimal("25.00"))
        self.assertTrue(
            Transaccion.objects.filter(
                billetera=self.billetera,
                tipo=Transaccion.Tipo.RETIRO,
                metodo=Transaccion.Metodo.TRANSFERENCIA,
                monto=Decimal("50.00"),
            ).exists()
        )
        self.assertTrue(Auditoria.objects.filter(usuario=self.user, accion="RETIRO_SALDO_API").exists())

    def test_api_retiros_rechaza_saldo_insuficiente(self):
        response = self.client.post(
            reverse("finanzas:api_retiros"),
            {
                "metodo": Transaccion.Metodo.YAPE_PLIN,
                "monto": "100.00",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["detalle"], "No cuentas con saldo suficiente para realizar este retiro.")

    def test_validacion_de_contrasena_devuelve_reglas_en_json(self):
        response = self.client.post(
            reverse("finanzas:validar_contrasena"),
            {
                "username": "tomi",
                "first_name": "Tomas",
                "last_name": "Perez",
                "email": "tomi@example.com",
                "password": "12345678",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(
            response.content,
            {
                "has_password": True,
                "similar": True,
                "min_length": True,
                "common": False,
                "numeric": False,
            },
        )

    def test_validacion_de_contrasena_vacia_devuelve_estado_neutro(self):
        response = self.client.post(
            reverse("finanzas:validar_contrasena"),
            {
                "username": "tomi",
                "first_name": "Tomas",
                "last_name": "Perez",
                "email": "tomi@example.com",
                "password": "",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(
            response.content,
            {
                "has_password": False,
                "similar": False,
                "min_length": False,
                "common": False,
                "numeric": False,
            },
        )

    def test_descarga_individual_pdf_devuelve_archivo(self):
        transaccion = Transaccion.objects.create(
            billetera=self.billetera,
            tipo=Transaccion.Tipo.RECARGA,
            metodo=Transaccion.Metodo.TARJETA,
            monto=Decimal("15.00"),
            descripcion="Recarga para prueba de PDF.",
        )

        response = self.client.get(reverse("finanzas:descargar_transaccion_pdf", args=[transaccion.id]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertIn(f"movimiento-{transaccion.id}.pdf", response["Content-Disposition"])

    def test_descarga_grupal_pdf_devuelve_archivo(self):
        primera = Transaccion.objects.create(
            billetera=self.billetera,
            tipo=Transaccion.Tipo.RECARGA,
            metodo=Transaccion.Metodo.TARJETA,
            monto=Decimal("15.00"),
            descripcion="Recarga uno.",
        )
        segunda = Transaccion.objects.create(
            billetera=self.billetera,
            tipo=Transaccion.Tipo.RECARGA,
            metodo=Transaccion.Metodo.YAPE_PLIN,
            monto=Decimal("35.00"),
            descripcion="Recarga dos.",
        )

        response = self.client.post(
            reverse("finanzas:descargar_transacciones_pdf"),
            {"transaccion_ids": [primera.id, segunda.id]},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertIn("movimientos-seleccionados.pdf", response["Content-Disposition"])
