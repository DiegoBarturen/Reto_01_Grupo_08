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

@login_required
@transaction.atomic
def realizar_apuesta(request):
    """Función blindada con Price Locking para asegurar la integridad de las cuotas"""
    if request.method == 'POST':
        evento_id = request.POST.get('evento_id')
        seleccion = request.POST.get('seleccion')
        monto = Decimal(request.POST.get('monto', '0'))
        cuota_solicitada = Decimal(request.POST.get('cuota', '0'))
        
        if monto <= 0:
            messages.error(request, "El monto debe ser mayor a 0.")
            return redirect('deportes:cartelera')

        evento = get_object_or_404(Evento, id=evento_id)
        cuota_obj = get_object_or_404(Cuota, evento=evento)
        
        if evento.estado == 'FINALIZADO' or evento.estado == 'SUSPENDIDO':
            messages.error(request, "Este evento ya no acepta apuestas.")
            return redirect('deportes:cartelera')

        cuota_real = cuota_obj.obtener_cuota_actual(seleccion)
        
        if cuota_real != cuota_solicitada:
            messages.error(request, f"¡La cuota ha cambiado! La cuota actual es {cuota_real}. Intenta de nuevo.")
            return redirect('deportes:cartelera')

        billetera_usuario, _ = Billetera.objects.select_for_update().get_or_create(usuario=request.user)
        billetera_pendientes, _ = Billetera.objects.get_or_create(tipo=Billetera.TipoCuenta.PENDIENTES)
        
        if billetera_usuario.saldo < monto:
            messages.error(request, "Saldo insuficiente.")
            return redirect('deportes:cartelera')

        tx_id = uuid.uuid4()
        
        LedgerEntry.objects.create(billetera=billetera_usuario, transaction_id=tx_id, direccion=LedgerEntry.Direccion.DEBIT, monto=monto, descripcion=f"Ticket Apuesta: {evento.equipo_local} vs {evento.equipo_visitante}")
        LedgerEntry.objects.create(billetera=billetera_pendientes, transaction_id=tx_id, direccion=LedgerEntry.Direccion.CREDIT, monto=monto, descripcion=f"Custodia de apuesta de {request.user.username}")

        apuesta = Apuesta(
            usuario=request.user,
            evento=evento,
            seleccion=seleccion,
            monto_apostado=monto,
            cuota_fijada=cuota_solicitada,
            estado=Apuesta.Estado.PENDIENTE
        )
        apuesta.save() 
        
        messages.success(request, f"¡Apuesta registrada! Cuota: {cuota_solicitada} | Ganancia: S/ {apuesta.ganancia_potencial:.2f}")
        return redirect('finanzas:billetera')
    
    return redirect('deportes:cartelera')

@staff_member_required(login_url='finanzas:login')
def lista_pendientes(request):
    """Muestra los partidos que tienen apuestas por liquidar"""
    eventos_ids = Apuesta.objects.filter(estado=Apuesta.Estado.PENDIENTE).values_list('evento_id', flat=True).distinct()
    eventos = Evento.objects.filter(id__in=eventos_ids).order_by('fecha_hora')
    
    return render(request, 'deportes/lista_pendientes.html', {'eventos': eventos})


@staff_member_required(login_url='finanzas:login')
@transaction.atomic
def liquidar_evento(request, evento_id):
    evento = get_object_or_404(Evento, id=evento_id)
    
    apuestas_pendientes = Apuesta.objects.select_for_update().filter(evento=evento, estado=Apuesta.Estado.PENDIENTE).select_related('usuario')

    if request.method == 'POST':
        resultado_partido = request.POST.get('resultado') # 'LOCAL', 'EMPATE' o 'VISITANTE'
        
        if resultado_partido in ['LOCAL', 'EMPATE', 'VISITANTE']:
            billetera_casa, _ = Billetera.objects.get_or_create(tipo=Billetera.TipoCuenta.CASA)
            billetera_pendientes, _ = Billetera.objects.get_or_create(tipo=Billetera.TipoCuenta.PENDIENTES)

            for apuesta in apuestas_pendientes:
                billetera_usuario = Billetera.objects.get(usuario=apuesta.usuario)
                tx_id = uuid.uuid4()
                
                monto_apostado = apuesta.monto_apostado 
                ganancia_neta = apuesta.ganancia_potencial - monto_apostado

                if apuesta.seleccion == resultado_partido:
                    LedgerEntry.objects.create(billetera=billetera_pendientes, transaction_id=tx_id, direccion=LedgerEntry.Direccion.DEBIT, monto=monto_apostado, descripcion=f"Devolución custodia - Apuesta #{apuesta.id}")
                    LedgerEntry.objects.create(billetera=billetera_usuario, transaction_id=tx_id, direccion=LedgerEntry.Direccion.CREDIT, monto=monto_apostado, descripcion=f"Devolución de stake - Apuesta #{apuesta.id}")
                    
                    if ganancia_neta > 0:
                        LedgerEntry.objects.create(billetera=billetera_casa, transaction_id=tx_id, direccion=LedgerEntry.Direccion.DEBIT, monto=ganancia_neta, descripcion=f"Pago de ganancia - Apuesta #{apuesta.id}")
                        LedgerEntry.objects.create(billetera=billetera_usuario, transaction_id=tx_id, direccion=LedgerEntry.Direccion.CREDIT, monto=ganancia_neta, descripcion=f"Premio ganado - Apuesta #{apuesta.id}")
                    
                    apuesta.estado = Apuesta.Estado.GANADA
                else:
                    LedgerEntry.objects.create(billetera=billetera_pendientes, transaction_id=tx_id, direccion=LedgerEntry.Direccion.DEBIT, monto=monto_apostado, descripcion=f"Cierre de custodia - Apuesta perdida #{apuesta.id}")
                    LedgerEntry.objects.create(billetera=billetera_casa, transaction_id=tx_id, direccion=LedgerEntry.Direccion.CREDIT, monto=monto_apostado, descripcion=f"Ingreso por apuesta perdida #{apuesta.id}")
                    
                    apuesta.estado = Apuesta.Estado.PERDIDA
                
                apuesta.save()
                
            evento.estado = 'FINALIZADO'
            evento.save()
            
            messages.success(request, f'¡Liquidación Masiva Completada! El sistema procesó los pagos al Ledger con resultado: {resultado_partido}.')
            return redirect('apuestas:lista_pendientes')
            
    return render(request, 'apuestas/liquidar_detalle.html', {
        'evento': evento,
        'apuestas': apuestas_pendientes
    })