from decimal import Decimal

from django.contrib import messages
from django.contrib.auth import login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import get_default_password_validators
from django.contrib.auth.views import LoginView
from django.db import transaction
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy

from .forms import (
    CambioContrasenaPerfilForm,
    LoginUsuarioForm,
    PerfilUsuarioForm,
    RecargaSaldoForm,
    RegistroUsuarioForm,
    RetiroSaldoForm,
)
from .models import Auditoria, Billetera, Transaccion
from .pdf_utils import generar_pdf_movimiento, generar_pdf_movimientos


def crear_auditoria(usuario, accion, detalle):
    Auditoria.objects.create(usuario=usuario, accion=accion, detalle=detalle)


def registro(request):
    if request.user.is_authenticated:
        return redirect("finanzas:billetera")

    if request.method == "POST":
        form = RegistroUsuarioForm(request.POST)
        if form.is_valid():
            user = form.save()
            Billetera.objects.create(usuario=user)
            crear_auditoria(
                user,
                "REGISTRO_USUARIO",
                f"Se registro el usuario {user.username} con billetera inicial en S/ 0.00.",
            )
            login(request, user)
            messages.success(request, "Tu cuenta fue creada correctamente.")
            return redirect("finanzas:billetera")
    else:
        form = RegistroUsuarioForm()

    return render(request, "finanzas/registro.html", {"form": form})


def validar_contrasena(request):
    if request.method != "POST":
        return JsonResponse({"detalle": "Metodo no permitido."}, status=405)

    password = request.POST.get("password", "")
    if not password:
        return JsonResponse(
            {
                "has_password": False,
                "similar": False,
                "min_length": False,
                "common": False,
                "numeric": False,
            }
        )

    candidate_user = User(
        username=request.POST.get("username", ""),
        first_name=request.POST.get("first_name", ""),
        last_name=request.POST.get("last_name", ""),
        email=request.POST.get("email", ""),
    )
    validators = get_default_password_validators()
    resultados = {
        "has_password": True,
        "similar": True,
        "min_length": True,
        "common": True,
        "numeric": True,
    }
    validator_map = {
        "UserAttributeSimilarityValidator": "similar",
        "MinimumLengthValidator": "min_length",
        "CommonPasswordValidator": "common",
        "NumericPasswordValidator": "numeric",
    }

    for validator in validators:
        key = validator_map.get(validator.__class__.__name__)
        if not key:
            continue
        try:
            validator.validate(password, candidate_user)
        except Exception:
            resultados[key] = False

    return JsonResponse(resultados)


class LoginUsuarioView(LoginView):
    template_name = "finanzas/login.html"
    authentication_form = LoginUsuarioForm
    redirect_authenticated_user = True

    def get_success_url(self):
        return reverse_lazy("finanzas:billetera")

    def form_valid(self, form):
        response = super().form_valid(form)
        crear_auditoria(
            self.request.user,
            "LOGIN_USUARIO",
            f"Inicio de sesion exitoso para {self.request.user.username}.",
        )
        return response


@login_required
def logout_usuario(request):
    if request.user.is_authenticated:
        crear_auditoria(
            request.user,
            "LOGOUT_USUARIO",
            f"Cierre de sesion del usuario {request.user.username}.",
        )
    logout(request)
    messages.info(request, "Tu sesion fue cerrada.")
    return redirect("finanzas:login")


@login_required
def billetera(request):
    billetera_usuario, _ = Billetera.objects.get_or_create(usuario=request.user)
    transacciones = billetera_usuario.transacciones.all()
    ultima_transaccion = transacciones.first()

    context = {
        "billetera": billetera_usuario,
        "transacciones": transacciones,
        "ultima_transaccion": ultima_transaccion,
    }
    return render(request, "finanzas/billetera.html", context)


@login_required
def recarga_saldo(request):
    billetera_usuario, _ = Billetera.objects.get_or_create(usuario=request.user)
    form = RecargaSaldoForm(initial={"monto": Decimal("50.00"), "metodo": Transaccion.Metodo.TARJETA})

    return render(
        request,
        "finanzas/recarga.html",
        {
            "billetera": billetera_usuario,
            "form": form,
        },
    )


@login_required
def retiro_saldo(request):
    billetera_usuario, _ = Billetera.objects.get_or_create(usuario=request.user)
    form = RetiroSaldoForm(initial={"monto": Decimal("50.00"), "metodo": Transaccion.Metodo.TRANSFERENCIA})

    return render(
        request,
        "finanzas/retiro.html",
        {
            "billetera": billetera_usuario,
            "form": form,
        },
    )


@login_required
@transaction.atomic
def recargar_saldo(request):
    if request.method != "POST":
        return redirect("finanzas:recarga")

    billetera_usuario = Billetera.objects.select_for_update().get(usuario=request.user)
    form = RecargaSaldoForm(request.POST)

    if not form.is_valid():
        return render(
            request,
            "finanzas/recarga.html",
            {
                "billetera": billetera_usuario,
                "form": form,
            },
            status=400,
        )

    monto = form.cleaned_data["monto"]
    metodo = form.cleaned_data["metodo"]
    billetera_usuario.saldo += monto
    billetera_usuario.save(update_fields=["saldo", "actualizado_en"])

    metodo_label = Transaccion.Metodo(metodo).label
    transaccion = Transaccion.objects.create(
        billetera=billetera_usuario,
        tipo=Transaccion.Tipo.RECARGA,
        metodo=metodo,
        monto=monto,
        descripcion=f"Recarga de saldo por S/ {monto} mediante {metodo_label.lower()}.",
    )
    crear_auditoria(
        request.user,
        "RECARGA_SALDO",
        f"El usuario recargo S/ {monto} mediante {metodo_label.lower()}. Nuevo saldo: S/ {billetera_usuario.saldo}.",
    )
    messages.success(request, f"Se recargaron S/ {monto} correctamente con {metodo_label.lower()}.")
    return redirect("finanzas:detalle_transaccion", transaccion_id=transaccion.id)


@login_required
@transaction.atomic
def retirar_saldo(request):
    if request.method != "POST":
        return redirect("finanzas:retiro")

    billetera_usuario = Billetera.objects.select_for_update().get(usuario=request.user)
    form = RetiroSaldoForm(request.POST)

    if not form.is_valid():
        return render(
            request,
            "finanzas/retiro.html",
            {
                "billetera": billetera_usuario,
                "form": form,
            },
            status=400,
        )

    monto = form.cleaned_data["monto"]
    metodo = form.cleaned_data["metodo"]

    if billetera_usuario.saldo < monto:
        form.add_error("monto", "No cuentas con saldo suficiente para realizar este retiro.")
        return render(
            request,
            "finanzas/retiro.html",
            {
                "billetera": billetera_usuario,
                "form": form,
            },
            status=400,
        )

    billetera_usuario.saldo -= monto
    billetera_usuario.save(update_fields=["saldo", "actualizado_en"])

    metodo_label = Transaccion.Metodo(metodo).label
    transaccion = Transaccion.objects.create(
        billetera=billetera_usuario,
        tipo=Transaccion.Tipo.RETIRO,
        metodo=metodo,
        monto=monto,
        descripcion=f"Retiro de saldo por S/ {monto} mediante {metodo_label.lower()}.",
    )
    crear_auditoria(
        request.user,
        "RETIRO_SALDO",
        f"El usuario retiro S/ {monto} mediante {metodo_label.lower()}. Nuevo saldo: S/ {billetera_usuario.saldo}.",
    )
    messages.success(request, f"Se retiro S/ {monto} correctamente con {metodo_label.lower()}.")
    return redirect("finanzas:detalle_transaccion", transaccion_id=transaccion.id)


@login_required
def detalle_transaccion(request, transaccion_id):
    billetera_usuario, _ = Billetera.objects.get_or_create(usuario=request.user)
    transaccion = get_object_or_404(
        Transaccion.objects.select_related("billetera", "billetera__usuario"),
        id=transaccion_id,
        billetera=billetera_usuario,
    )

    return render(
        request,
        "finanzas/detalle_transaccion.html",
        {
            "billetera": billetera_usuario,
            "transaccion": transaccion,
        },
    )


@login_required
def descargar_transaccion_pdf(request, transaccion_id):
    billetera_usuario, _ = Billetera.objects.get_or_create(usuario=request.user)
    transaccion = get_object_or_404(
        Transaccion.objects.select_related("billetera", "billetera__usuario"),
        id=transaccion_id,
        billetera=billetera_usuario,
    )
    pdf_buffer = generar_pdf_movimiento(transaccion, billetera_usuario)
    response = HttpResponse(pdf_buffer.getvalue(), content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="movimiento-{transaccion.id}.pdf"'
    return response


@login_required
def descargar_transacciones_pdf(request):
    if request.method != "POST":
        return redirect("finanzas:billetera")

    billetera_usuario, _ = Billetera.objects.get_or_create(usuario=request.user)
    ids = request.POST.getlist("transaccion_ids")
    if not ids:
        messages.error(request, "Selecciona al menos un movimiento para descargar el PDF.")
        return redirect("finanzas:billetera")

    transacciones = list(billetera_usuario.transacciones.filter(id__in=ids).order_by("-creado_en"))
    if not transacciones:
        messages.error(request, "No se encontraron movimientos validos para descargar.")
        return redirect("finanzas:billetera")

    pdf_buffer = generar_pdf_movimientos(transacciones, billetera_usuario)
    response = HttpResponse(pdf_buffer.getvalue(), content_type="application/pdf")
    response["Content-Disposition"] = 'attachment; filename="movimientos-seleccionados.pdf"'
    return response


@login_required
def configuracion_perfil(request):
    billetera_usuario, _ = Billetera.objects.get_or_create(usuario=request.user)

    if request.method == "POST":
        if request.POST.get("form_type") == "perfil":
            perfil_form = PerfilUsuarioForm(request.POST, instance=request.user)
            password_form = CambioContrasenaPerfilForm(request.user)

            if perfil_form.is_valid():
                usuario_actualizado = perfil_form.save()
                crear_auditoria(
                    usuario_actualizado,
                    "ACTUALIZACION_PERFIL",
                    f"El usuario actualizo sus datos de perfil. Nuevo username: {usuario_actualizado.username}.",
                )
                messages.success(request, "Tu informacion de perfil fue actualizada.")
                return redirect("finanzas:perfil")
        else:
            perfil_form = PerfilUsuarioForm(instance=request.user)
            password_form = CambioContrasenaPerfilForm(request.user, request.POST)

            if password_form.is_valid():
                usuario_actualizado = password_form.save()
                update_session_auth_hash(request, usuario_actualizado)
                crear_auditoria(
                    usuario_actualizado,
                    "CAMBIO_CONTRASENA",
                    "El usuario actualizo la contrasena de su cuenta.",
                )
                messages.success(request, "Tu contrasena fue actualizada correctamente.")
                return redirect("finanzas:perfil")
    else:
        perfil_form = PerfilUsuarioForm(instance=request.user)
        password_form = CambioContrasenaPerfilForm(request.user)

    return render(
        request,
        "finanzas/perfil.html",
        {
            "billetera": billetera_usuario,
            "perfil_form": perfil_form,
            "password_form": password_form,
        },
    )
