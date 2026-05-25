from django.urls import path

from .api_views import BilleteraAPIView, RecargaAPIView, RetiroAPIView, TransaccionListAPIView
from .views import (
    LoginUsuarioView,
    billetera,
    configuracion_perfil,
    descargar_transaccion_pdf,
    descargar_transacciones_pdf,
    detalle_transaccion,
    logout_usuario,
    recarga_saldo,
    recargar_saldo,
    registro,
    retiro_saldo,
    retirar_saldo,
    validar_contrasena,
)

app_name = "finanzas"

urlpatterns = [
    path("", billetera, name="inicio"),
    path("registro/", registro, name="registro"),
    path("login/", LoginUsuarioView.as_view(), name="login"),
    path("logout/", logout_usuario, name="logout"),
    path("registro/validar-contrasena/", validar_contrasena, name="validar_contrasena"),
    path("billetera/", billetera, name="billetera"),
    path("perfil/", configuracion_perfil, name="perfil"),
    path("billetera/recarga/", recarga_saldo, name="recarga"),
    path("billetera/recargar/", recargar_saldo, name="recargar_saldo"),
    path("billetera/retiro/", retiro_saldo, name="retiro"),
    path("billetera/retirar/", retirar_saldo, name="retirar_saldo"),
    path("billetera/transacciones/<int:transaccion_id>/", detalle_transaccion, name="detalle_transaccion"),
    path("billetera/transacciones/<int:transaccion_id>/pdf/", descargar_transaccion_pdf, name="descargar_transaccion_pdf"),
    path("billetera/transacciones/pdf/", descargar_transacciones_pdf, name="descargar_transacciones_pdf"),
    path("api/billetera/", BilleteraAPIView.as_view(), name="api_billetera"),
    path("api/transacciones/", TransaccionListAPIView.as_view(), name="api_transacciones"),
    path("api/recargas/", RecargaAPIView.as_view(), name="api_recargas"),
    path("api/retiros/", RetiroAPIView.as_view(), name="api_retiros"),
]
