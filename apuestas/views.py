from decimal import Decimal
import uuid
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.contrib import messages
from .models import Apuesta
from deportes.models import Evento, Cuota
from finanzas.models import Billetera, LedgerEntry
from django.core.paginator import Paginator
from .filters import ApuestaFilter

@staff_member_required(login_url='finanzas:login')
def lista_pendientes(request):
    # 1. Obtenemos el QuerySet base
    qs = Apuesta.objects.filter(estado=Apuesta.Estado.PENDIENTE).select_related('usuario', 'evento')
    
    # 2. Aplicamos los filtros
    f = ApuestaFilter(request.GET, queryset=qs)
    
    # 3. Paginación (20 resultados por página)
    paginator = Paginator(f.qs, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'deportes/lista_pendientes.html', {
        'filter': f,
        'page_obj': page_obj
    })

@login_required
@transaction.atomic
def realizar_apuesta(request):
    """Función blindada con Price Locking para asegurar la integridad de las cuotas"""
    if request.method == 'POST':
        evento_id = request.POST.get('evento_id')
        seleccion = request.POST.get('seleccion')
        monto = Decimal(request.POST.get('monto', '0'))
        cuota_solicitada = Decimal(request.POST.get('cuota', '0')) # Lo que el JS envió
        
        if monto <= 0:
            messages.error(request, "El monto debe ser mayor a 0.")
            return redirect('deportes:cartelera')

        # 1. Obtenemos el evento y la cuota REAL desde la BD
        evento = get_object_or_404(Evento, id=evento_id)
        cuota_obj = get_object_or_404(Cuota, evento=evento)
        
        # 2. VALIDACIÓN DE ESTADO
        if evento.estado == 'FINALIZADO':
            messages.error(request, "Este evento ya no acepta apuestas.")
            return redirect('deportes:cartelera')

        # 3. EL CANDADO (PRICE LOCKING)
        # Comparamos la cuota que el usuario ve en pantalla con la que tenemos en la BD
        cuota_real = cuota_obj.obtener_cuota_actual(seleccion)
        
        if cuota_real != cuota_solicitada:
            messages.error(request, f"¡La cuota ha cambiado! La cuota actual es {cuota_real}. Intenta de nuevo.")
            return redirect('deportes:cartelera')

        # 4. PROCESO FINANCIERO (Partida Doble)
        # Bloqueamos la billetera del usuario para evitar concurrencia
        billetera_usuario, _ = Billetera.objects.select_for_update().get_or_create(usuario=request.user)
        billetera_pendientes, _ = Billetera.objects.get_or_create(tipo=Billetera.TipoCuenta.PENDIENTES)
        
        if billetera_usuario.saldo < monto:
            messages.error(request, "Saldo insuficiente.")
            return redirect('deportes:cartelera')

        tx_id = uuid.uuid4()
        
        # Débito del usuario / Crédito a Pendientes (Custodia)
        LedgerEntry.objects.create(billetera=billetera_usuario, transaction_id=tx_id, direccion=LedgerEntry.Direccion.DEBIT, monto=monto, descripcion=f"Ticket Apuesta: {evento.equipo_local} vs {evento.equipo_visitante}")
        LedgerEntry.objects.create(billetera=billetera_pendientes, transaction_id=tx_id, direccion=LedgerEntry.Direccion.CREDIT, monto=monto, descripcion=f"Custodia de apuesta de {request.user.username}")

        # Guardamos el ticket
        apuesta = Apuesta(
            usuario=request.user,
            evento=evento,
            seleccion=seleccion,
            monto_apostado=monto,
            cuota_fijada=cuota_solicitada, # Guardamos la cuota que validamos
            estado=Apuesta.Estado.PENDIENTE
        )
        apuesta.save() 
        
        messages.success(request, f"¡Apuesta registrada! Cuota: {cuota_solicitada} | Ganancia: S/ {apuesta.ganancia_potencial:.2f}")
        return redirect('finanzas:billetera')
    
    return redirect('deportes:cartelera')

@staff_member_required(login_url='finanzas:login')
@transaction.atomic
def liquidar_apuesta(request, apuesta_id, resultado):
    """Función para el Administrador: define si la casa paga o cobra"""
    apuesta = get_object_or_404(Apuesta.objects.select_for_update(), id=apuesta_id)
    
    if apuesta.estado != Apuesta.Estado.PENDIENTE:
        messages.error(request, "Esta apuesta ya fue liquidada previamente.")
        return redirect('apuestas:lista_pendientes')

    # Obtenemos las 3 cuentas involucradas
    billetera_usuario = Billetera.objects.get(usuario=apuesta.usuario)
    billetera_casa, _ = Billetera.objects.get_or_create(tipo=Billetera.TipoCuenta.CASA)
    billetera_pendientes, _ = Billetera.objects.get_or_create(tipo=Billetera.TipoCuenta.PENDIENTES)

    tx_id = uuid.uuid4()
    
    # Ajustado con tus nombres de campos exactos
    monto_apostado = apuesta.monto_apostado 
    ganancia_neta = apuesta.ganancia_potencial - monto_apostado

    if resultado == 'GANADA':
        # 1. Liberamos el dinero en custodia y se lo devolvemos al usuario
        LedgerEntry.objects.create(billetera=billetera_pendientes, transaction_id=tx_id, direccion=LedgerEntry.Direccion.DEBIT, monto=monto_apostado, descripcion=f"Devolución de custodia - Apuesta #{apuesta.id}")
        LedgerEntry.objects.create(billetera=billetera_usuario, transaction_id=tx_id, direccion=LedgerEntry.Direccion.CREDIT, monto=monto_apostado, descripcion=f"Devolución de stake - Apuesta #{apuesta.id}")
        
        # 2. La Casa paga la ganancia desde sus propios fondos
        if ganancia_neta > 0:
            LedgerEntry.objects.create(billetera=billetera_casa, transaction_id=tx_id, direccion=LedgerEntry.Direccion.DEBIT, monto=ganancia_neta, descripcion=f"Pago de ganancia - Apuesta #{apuesta.id}")
            LedgerEntry.objects.create(billetera=billetera_usuario, transaction_id=tx_id, direccion=LedgerEntry.Direccion.CREDIT, monto=ganancia_neta, descripcion=f"Premio ganado - Apuesta #{apuesta.id}")
        
        apuesta.estado = Apuesta.Estado.GANADA
    else:
        # Si pierde, el dinero en custodia pasa a ser ingreso de la Casa
        LedgerEntry.objects.create(billetera=billetera_pendientes, transaction_id=tx_id, direccion=LedgerEntry.Direccion.DEBIT, monto=monto_apostado, descripcion=f"Cierre de custodia - Apuesta perdida #{apuesta.id}")
        LedgerEntry.objects.create(billetera=billetera_casa, transaction_id=tx_id, direccion=LedgerEntry.Direccion.CREDIT, monto=monto_apostado, descripcion=f"Ingreso por apuesta perdida #{apuesta.id}")
        
        apuesta.estado = Apuesta.Estado.PERDIDA
    
    apuesta.save()
    messages.success(request, f"Apuesta #{apuesta.id} marcada como {resultado}.")
    return redirect('apuestas:lista_pendientes')