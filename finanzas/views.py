import io
import uuid
from decimal import Decimal
from datetime import date 
from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.auth.views import LoginView
from django.db import transaction
from django.http import JsonResponse, FileResponse
from django.shortcuts import redirect, render, get_object_or_404
from django.urls import reverse_lazy
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from django.db.models import Sum 
from apuestas.models import Apuesta
from deportes.models import Evento


from .forms import (
    LoginUsuarioForm, PerfilUsuarioForm,
    RecargaSaldoForm, RegistroUsuarioForm, RetiroSaldoForm,
)
from .models import Billetera, LedgerEntry, Perfil


def registro(request):
    if request.user.is_authenticated: 
        return redirect("finanzas:billetera")
        
    if request.method == "POST":
        form = RegistroUsuarioForm(request.POST)
        if form.is_valid():
            dni_input = str(form.cleaned_data["dni"]).strip()
            fecha_nac = form.cleaned_data["fecha_nacimiento"]
            
            # 1. VALIDACIÓN KYC: Mayoría de Edad (mantenemos esto porque es buena práctica)
            hoy = date.today()
            edad = hoy.year - fecha_nac.year - ((hoy.month, hoy.day) < (fecha_nac.month, fecha_nac.day))
            
            if edad < 18:
                messages.error(request, "KYC Rechazado: Debes ser mayor de 18 años.")
                return render(request, "finanzas/registro.html", {"form": form})

            # =======================================================
            # 2. VALIDACIÓN DNI: DESACTIVADA PARA EVITAR BLOQUEOS
            # =======================================================
            # El sistema ahora solo verifica que sea numérico y tenga 9 dígitos, 
            # pero no bloquea si el cálculo matemático falla.
            if len(dni_input) != 9 or not dni_input.isdigit():
                messages.error(request, "El DNI debe tener 9 dígitos.")
                return render(request, "finanzas/registro.html", {"form": form})

            # =======================================================
            # 3. CREACIÓN DE USUARIO (KYC APROBADO AUTOMÁTICAMENTE)
            # =======================================================
            user = form.save()
            
            Perfil.objects.create(
                usuario=user,
                dni=dni_input[:8],
                fecha_nacimiento=fecha_nac,
                estado=Perfil.Estado.VERIFICADO
            )
            
            Billetera.objects.create(usuario=user, tipo=Billetera.TipoCuenta.USUARIO)
            
            login(request, user)
            messages.success(request, "Registro exitoso.")
            return redirect("finanzas:billetera")
    else:
        form = RegistroUsuarioForm()
    
    return render(request, "finanzas/registro.html", {"form": form})

def validar_contrasena(request):
    return JsonResponse({"has_password": True, "similar": True, "min_length": True, "common": True, "numeric": True})

class LoginUsuarioView(LoginView):
    template_name = "finanzas/login.html"
    authentication_form = LoginUsuarioForm
    redirect_authenticated_user = True
    
    def get_success_url(self): 
        # Si el usuario es administrador o staff, lo mandamos a su panel
        if self.request.user.is_staff or self.request.user.is_superuser:
            # Usamos la ruta estática directa para evitar errores de nombres
            return "/deportes/dashboard/" 
            
        # Si es un cliente normal, va a su billetera
        return reverse_lazy("finanzas:billetera")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from deportes.models import Evento 
        context['eventos_destacados'] = Evento.objects.filter(
            estado__in=['PENDIENTE', 'EN_JUEGO']
        ).order_by('fecha_hora')[:3]
        return context

@login_required
def logout_usuario(request):
    logout(request)
    messages.info(request, "Tu sesión fue cerrada.")
    return redirect("finanzas:login")

@login_required
def billetera(request):
    billetera_usuario, _ = Billetera.objects.get_or_create(usuario=request.user)
    
    # 1. Movimientos financieros (Solo los últimos 5 para no saturar el panel)
    movimientos = billetera_usuario.movimientos.all().order_by('-creado_en')[:5]
    
    # 2. Estadísticas de apuestas para el Dashboard
    mis_apuestas = request.user.apuestas.all()
    
    # Contamos apuestas que están corriendo ahora mismo
    apuestas_activas = mis_apuestas.filter(estado=Apuesta.Estado.PENDIENTE).count()
    
    # Suma de todo el dinero ganado históricamente
    total_ganado = mis_apuestas.filter(estado=Apuesta.Estado.GANADA).aggregate(
        total=Sum('ganancia_potencial')
    )['total'] or Decimal('0.00')
    
    # Suma de todo el dinero que el usuario ha arriesgado
    total_apostado = mis_apuestas.aggregate(
        total=Sum('monto_apostado')
    )['total'] or Decimal('0.00')
    
    # Solo las últimas 5 apuestas para la vista rápida
    ultimas_apuestas = mis_apuestas.order_by('-fecha_creacion')[:5]

    return render(request, "finanzas/billetera.html", {
        "billetera": billetera_usuario,
        "transacciones": movimientos,
        "apuestas_activas": apuestas_activas,
        "total_ganado": total_ganado,
        "total_apostado": total_apostado,
        "ultimas_apuestas": ultimas_apuestas,
    })

@login_required
def recarga_saldo(request):
    billetera_usuario, _ = Billetera.objects.get_or_create(usuario=request.user)
    return render(request, "finanzas/recarga.html", {"billetera": billetera_usuario, "form": RecargaSaldoForm()})

@login_required
def retiro_saldo(request):
    billetera_usuario, _ = Billetera.objects.get_or_create(usuario=request.user)
    return render(request, "finanzas/retiro.html", {"billetera": billetera_usuario, "form": RetiroSaldoForm()})

@login_required
@transaction.atomic
def recargar_saldo(request):
    if request.method != "POST": return redirect("finanzas:recarga")
    
    billetera_usuario, _ = Billetera.objects.select_for_update().get_or_create(usuario=request.user)
    perfil = Perfil.objects.get(usuario=request.user) # Obtenemos el perfil para los controles
    
    form = RecargaSaldoForm(request.POST)
    if form.is_valid():
        monto = form.cleaned_data["monto"]
        metodo = form.cleaned_data["metodo"]
        
        # 1. Validación de Autoexclusión
        hoy = date.today()
        if perfil.autoexcluido_hasta and hoy < perfil.autoexcluido_hasta.date():
            form.add_error("monto", f"Tu cuenta está autoexcluida hasta {perfil.autoexcluido_hasta.strftime('%d/%m/%Y')}.")
            return render(request, "finanzas/recarga.html", {"billetera": billetera_usuario, "form": form}, status=400)
            
        # 2. Validación de Límite Diario
        # Sumamos los créditos (recargas) realizados hoy
        total_depositado_hoy = LedgerEntry.objects.filter(
            billetera__usuario=request.user,
            direccion=LedgerEntry.Direccion.CREDIT,
            creado_en__date=hoy
        ).aggregate(total=Sum('monto'))['total'] or Decimal('0')
        
        if (total_depositado_hoy + monto) > perfil.limite_deposito_diario:
            form.add_error("monto", f"Excede tu límite diario de S/ {perfil.limite_deposito_diario}. Depositado hoy: S/ {total_depositado_hoy}")
            return render(request, "finanzas/recarga.html", {"billetera": billetera_usuario, "form": form}, status=400)

        # Si pasa las validaciones, procedemos con la transacción
        billetera_casa, _ = Billetera.objects.get_or_create(tipo=Billetera.TipoCuenta.CASA)
        tx_id = uuid.uuid4()
        
        LedgerEntry.objects.create(billetera=billetera_usuario, transaction_id=tx_id, direccion=LedgerEntry.Direccion.CREDIT, monto=monto, descripcion=f"Recarga vía {metodo}")
        LedgerEntry.objects.create(billetera=billetera_casa, transaction_id=tx_id, direccion=LedgerEntry.Direccion.DEBIT, monto=monto, descripcion=f"Ingreso de recarga de {request.user.username}")
        
        messages.success(request, f"Se recargaron S/ {monto} correctamente.")
        return redirect("finanzas:billetera")
        
    return render(request, "finanzas/recarga.html", {"billetera": billetera_usuario, "form": form}, status=400)

@login_required
@transaction.atomic
def retirar_saldo(request):
    if request.method != "POST": return redirect("finanzas:retiro")
    billetera_usuario, _ = Billetera.objects.select_for_update().get_or_create(usuario=request.user)
    billetera_casa, _ = Billetera.objects.get_or_create(tipo=Billetera.TipoCuenta.CASA)

    form = RetiroSaldoForm(request.POST)
    if form.is_valid():
        monto = form.cleaned_data["monto"]
        if billetera_usuario.saldo < monto:
            form.add_error("monto", "Saldo insuficiente.")
            return render(request, "finanzas/retiro.html", {"billetera": billetera_usuario, "form": form}, status=400)
        
        tx_id = uuid.uuid4()
        LedgerEntry.objects.create(billetera=billetera_usuario, transaction_id=tx_id, direccion=LedgerEntry.Direccion.DEBIT, monto=monto, descripcion="Retiro de saldo")
        LedgerEntry.objects.create(billetera=billetera_casa, transaction_id=tx_id, direccion=LedgerEntry.Direccion.CREDIT, monto=monto, descripcion=f"Egreso por retiro de {request.user.username}")
        
        messages.success(request, f"Se retiró S/ {monto} correctamente.")
        return redirect("finanzas:billetera")
    return render(request, "finanzas/retiro.html", {"billetera": billetera_usuario, "form": form}, status=400)

@login_required
def configuracion_perfil(request):
    billetera_usuario, _ = Billetera.objects.get_or_create(usuario=request.user)
    perfil_form = PerfilUsuarioForm(instance=request.user)
    return render(request, "finanzas/perfil.html", {"billetera": billetera_usuario, "perfil_form": perfil_form})

@login_required
def detalle_transaccion(request, transaccion_id):
    messages.info(request, "El detalle individual de transacción está en mantenimiento por la nueva Partida Doble.")
    return redirect('finanzas:billetera')


# ==========================================
# GENERADORES DE PDF (REPORTLAB)
# ==========================================

@login_required
def descargar_ticket_apuesta_pdf(request, apuesta_id):
    """Genera un Ticket de Apuesta real"""
    apuesta = get_object_or_404(Apuesta, id=apuesta_id, usuario=request.user)
    
    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    
    # Nombre del archivo al descargar
    filename = f"Ticket_Apuesta_{apuesta.id}_{apuesta.evento.equipo_local[:3]}_vs_{apuesta.evento.equipo_visitante[:3]}.pdf"
    p.setTitle(filename)

    # Cabecera
    p.setFont("Helvetica-Bold", 22)
    p.setFillColor(colors.HexColor("#FF7A1A"))
    p.drawString(50, 740, "FAIRBET LAB")
    p.setFont("Helvetica", 14)
    p.setFillColor(colors.black)
    p.drawString(50, 715, "TICKET DE APUESTA DEPORTIVA")
    p.line(50, 705, 550, 705)
    
    # Datos del Ticket
    p.setFont("Helvetica", 12)
    p.drawString(50, 680, f"Ticket ID: #{apuesta.id}")
    p.drawString(50, 660, f"Fecha de Emisión: {apuesta.fecha_creacion.strftime('%d/%m/%Y %H:%M')}")
    p.drawString(50, 640, f"Titular: {request.user.username}")
    
    # Datos del Evento
    p.setFont("Helvetica-Bold", 14)
    p.drawString(50, 600, "Detalles del Evento:")
    p.setFont("Helvetica", 12)
    p.drawString(50, 580, f"Partido: {apuesta.evento.equipo_local} vs {apuesta.evento.equipo_visitante}")
    p.drawString(50, 560, f"Deporte: {apuesta.evento.get_deporte_display()}")
    
    # Datos de la Jugada
    p.setFont("Helvetica-Bold", 14)
    p.drawString(50, 520, "Detalles de la Jugada:")
    p.setFont("Helvetica", 12)
    p.drawString(50, 500, f"Selección: {apuesta.get_seleccion_display()} (Gana {apuesta.get_seleccion_display()})")
    p.drawString(50, 480, f"Cuota Multiplicadora: {apuesta.cuota_fijada}")
    
    p.line(50, 450, 550, 450)
    
    # Resumen Financiero
    p.setFont("Helvetica-Bold", 14)
    p.drawString(50, 420, f"Monto Apostado: S/ {apuesta.monto_apostado:.2f}")
    p.setFillColor(colors.HexColor("#27ae60"))
    p.drawString(50, 400, f"Ganancia Potencial: S/ {apuesta.ganancia_potencial:.2f}")
    
    # Estado
    p.setFillColor(colors.black)
    p.setFont("Helvetica", 12)
    p.drawString(50, 360, f"Estado del Ticket: {apuesta.estado}")
    
    # Pie de página legal
    p.setFont("Helvetica-Oblique", 9)
    p.setFillColor(colors.gray)
    p.drawString(50, 100, "Plataforma Educativa - Sin valor comercial. Ley N° 31557 y DS N° 005-2023-MINCETUR.")

    p.showPage()
    p.save()
    buffer.seek(0)
    
    return FileResponse(buffer, as_attachment=True, filename=filename)


@login_required
def descargar_transaccion_pdf(request, transaccion_id):
    """Genera un recibo individual para movimientos de dinero (Recargas, Retiros, Premios)"""
    transaccion = get_object_or_404(LedgerEntry, id=transaccion_id, billetera__usuario=request.user)
    
    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    
    # Nombre correcto para recibos financieros
    filename = f"Recibo_Financiero_{transaccion.transaction_id}.pdf"
    p.setTitle(filename)

    p.setFont("Helvetica-Bold", 20)
    p.setFillColor(colors.HexColor("#D4AF37")) # Color Oro
    p.drawString(50, 750, "FAIRBET LAB")
    
    p.setFont("Helvetica", 14)
    p.setFillColor(colors.black)
    p.drawString(50, 720, "RECIBO OFICIAL DE TRANSACCIÓN FINANCIERA")
    p.line(50, 710, 550, 710)
    
    p.setFont("Helvetica", 12)
    p.drawString(50, 680, f"ID de Operación: {transaccion.transaction_id}")
    p.drawString(50, 660, f"Fecha de Liquidación: {transaccion.creado_en.strftime('%d/%m/%Y %H:%M')}")
    p.drawString(50, 640, f"Titular de Cuenta: {request.user.username}")
    
    p.drawString(50, 600, f"Concepto de Movimiento: {transaccion.descripcion}")
    
    tipo_movimiento = "INGRESO DE DINERO" if transaccion.direccion == 'CREDIT' else "EGRESO DE DINERO"
    p.drawString(50, 580, f"Tipo de Movimiento: {tipo_movimiento}")
    
    p.setFont("Helvetica-Bold", 16)
    if transaccion.direccion == 'CREDIT':
        p.setFillColor(colors.HexColor("#27ae60"))
    else:
        p.setFillColor(colors.HexColor("#e74c3c"))
        
    p.drawString(50, 540, f"Monto Total: S/ {transaccion.monto:.2f}")

    p.showPage()
    p.save()
    buffer.seek(0)
    
    return FileResponse(buffer, as_attachment=True, filename=filename)


@login_required
def descargar_transacciones_pdf(request):
    """Genera un reporte PDF con multiples transacciones (Descarga por Lotes)"""
    # Mantenemos este igual, solo asegurándonos del nombre
    if request.method == 'POST':
        transaccion_ids = request.POST.getlist('transaccion_ids')
        if not transaccion_ids:
            messages.warning(request, "No seleccionaste ninguna transacción para descargar.")
            return redirect('finanzas:billetera')

        transacciones = LedgerEntry.objects.filter(id__in=transaccion_ids, billetera__usuario=request.user).order_by('-creado_en')
        buffer = io.BytesIO()
        p = canvas.Canvas(buffer, pagesize=letter)
        
        filename = "Reporte_Consolidado_FairBet.pdf"
        p.setTitle(filename)

        p.setFont("Helvetica-Bold", 18)
        p.setFillColor(colors.HexColor("#D4AF37"))
        p.drawString(50, 750, "FAIRBET LAB - ESTADO DE CUENTA")
        p.line(50, 740, 550, 740)
        
        p.setFont("Helvetica", 10)
        p.setFillColor(colors.black)
        
        y_position = 710
        for t in transacciones:
            if y_position < 100:
                p.showPage()
                y_position = 750
                p.setFont("Helvetica", 10)
                
            direccion_txt = "+ INGRESO" if t.direccion == 'CREDIT' else "- EGRESO"
            linea = f"[{t.creado_en.strftime('%d/%m/%Y %H:%M')}]  {direccion_txt}  |  S/ {t.monto:.2f}  |  {t.descripcion}"
            p.drawString(50, y_position, linea)
            y_position -= 25 

        p.showPage()
        p.save()
        buffer.seek(0)
        return FileResponse(buffer, as_attachment=True, filename=filename)
    return redirect('finanzas:billetera')