from django.urls import path
from .api_views import (
    api_consultar_saldo,
    api_listar_movimientos_billetera,
    api_recargar_saldo,
    api_registrar_usuario,
    api_retirar_saldo,
)
from .views import (
    LoginUsuarioView, billetera, configuracion_perfil,
    logout_usuario, recarga_saldo, recargar_saldo,
    registro, retiro_saldo, retirar_saldo, validar_contrasena,
    descargar_transacciones_pdf,
    detalle_transaccion,          
    descargar_transaccion_pdf, 
    descargar_ticket_apuesta_pdf
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
    path("billetera/descargar-pdf/", descargar_transacciones_pdf, name="descargar_transacciones_pdf"),
    path("billetera/detalle/<int:transaccion_id>/", detalle_transaccion, name="detalle_transaccion"),
    path("billetera/descargar-pdf/<int:transaccion_id>/", descargar_transaccion_pdf, name="descargar_transaccion_pdf"),
    path("api/registro/", api_registrar_usuario, name="api_registrar_usuario"),
    path("api/billetera/saldo/", api_consultar_saldo, name="api_consultar_saldo"),
    path("api/billetera/movimientos/", api_listar_movimientos_billetera, name="api_listar_movimientos_billetera"),
    path("api/billetera/recargar/", api_recargar_saldo, name="api_recargar_saldo"),
    path("api/billetera/retirar/", api_retirar_saldo, name="api_retirar_saldo"),
    path('apuesta/<int:apuesta_id>/ticket/', descargar_ticket_apuesta_pdf, name='descargar_ticket_apuesta_pdf'),
]
