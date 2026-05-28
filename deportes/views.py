from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from django.db.models import Sum, ProtectedError
from django.http import JsonResponse

# Importaciones de modelos locales
from .models import Evento, Cuota
from .forms import EventoForm, CuotaForm

# Importaciones de otras apps para el dashboard
from apuestas.models import Apuesta
from finanzas.models import LedgerEntry, Billetera


def cartelera(request):
    billetera_usuario = None
    if request.user.is_authenticated:
        # Traemos la billetera si el usuario está logueado
        billetera_usuario, _ = Billetera.objects.get_or_create(usuario=request.user)
    
    eventos = Evento.objects.all().order_by('fecha_hora')
    
    return render(request, 'deportes/cartelera.html', {
        'eventos': eventos,
        'billetera': billetera_usuario # <--- Enviamos la billetera al template
    })

@staff_member_required(login_url='finanzas:login')
def dashboard_admin(request):
    """Centro de mando contable y operativo para el Administrador"""
    
    # 1. Total de dinero que ha ingresado al sistema 
    # CAMBIO AQUÍ: Ahora sumamos todos los créditos (ingresos) que han entrado a la Casa
    total_ingresos = LedgerEntry.objects.filter(
        billetera__tipo='CASA', 
        direccion='CREDIT'
    ).aggregate(Sum('monto'))['monto__sum'] or 0.0

    # 2. Capital Comprometido (Apuestas pendientes)
    total_por_liquidar = Apuesta.objects.filter(estado='PENDIENTE').aggregate(Sum('ganancia_potencial'))['ganancia_potencial__sum'] or 0.0

    # 3. Registro y trazabilidad de los clientes
    historial_apuestas = Apuesta.objects.select_related('usuario', 'evento').order_by('-id')[:10]

    context = {
        'total_ingresos': total_ingresos,
        'total_por_liquidar': total_por_liquidar,
        'historial_apuestas': historial_apuestas,
    }
    return render(request, 'deportes/dashboard_admin.html', context)

@staff_member_required(login_url='finanzas:login')
def crear_partido(request):
    if request.method == 'POST':
        evento_form = EventoForm(request.POST)
        cuota_form = CuotaForm(request.POST)
        
        if evento_form.is_valid() and cuota_form.is_valid():
            evento = evento_form.save()
            cuota = cuota_form.save(commit=False)
            cuota.evento = evento
            cuota.save()
            messages.success(request, '¡Partido y cuotas creados exitosamente!')
            
            # ✅ CORRECCIÓN APLICADA: Redirigimos al panel de gestión en lugar del cliente
            return redirect('deportes:gestionar_eventos')
    else:
        evento_form = EventoForm()
        cuota_form = CuotaForm()

    return render(request, 'deportes/crear_partido.html', {
        'evento_form': evento_form,
        'cuota_form': cuota_form
    })

def api_obtener_cuotas(request):
    """API que devuelve las cuotas actuales de todos los eventos activos en formato JSON"""
    eventos = Evento.objects.filter(estado__in=['PENDIENTE', 'EN_JUEGO'])
    data = {}
    for ev in eventos:
        if hasattr(ev, 'cuotas'):
            data[ev.id] = {
                'local': str(ev.cuotas.paga_local),
                'empate': str(ev.cuotas.paga_empate),
                'visita': str(ev.cuotas.paga_visitante)
            }
    return JsonResponse(data)

@staff_member_required(login_url='finanzas:login')
def gestionar_eventos(request):
    """Vista principal de la Cartelera del Administrador (Read)"""
    eventos = Evento.objects.all().order_by('-fecha_hora')
    return render(request, 'deportes/gestionar_eventos.html', {'eventos': eventos})

@staff_member_required(login_url='finanzas:login')
def editar_evento(request, evento_id):
    """Permite modificar estados (ej. PENDIENTE a EN_JUEGO) y actualizar cuotas en vivo (Update)"""
    evento = get_object_or_404(Evento, id=evento_id)
    cuota = get_object_or_404(Cuota, evento=evento)

    if request.method == 'POST':
        evento_form = EventoForm(request.POST, instance=evento)
        cuota_form = CuotaForm(request.POST, instance=cuota)
        
        if evento_form.is_valid() and cuota_form.is_valid():
            evento_form.save()
            cuota_form.save()
            messages.success(request, f'Evento "{evento.equipo_local} vs {evento.equipo_visitante}" actualizado correctamente.')
            return redirect('deportes:gestionar_eventos')
    else:
        evento_form = EventoForm(instance=evento)
        cuota_form = CuotaForm(instance=cuota)

    return render(request, 'deportes/editar_partido.html', {
        'evento_form': evento_form,
        'cuota_form': cuota_form,
        'evento': evento
    })

@staff_member_required(login_url='finanzas:login')
def eliminar_evento(request, evento_id):
    evento = get_object_or_404(Evento, id=evento_id)
    
    # =========================================================
    # REGLA 1: El evento debe estar FINALIZADO o ANULADO
    # =========================================================
    if evento.estado not in ['FINALIZADO', 'ANULADO']:
        messages.error(
            request, 
            f'🛑 DENEGADO: El partido está "{evento.get_estado_display()}". '
            'Solo puedes eliminar eventos que ya hayan finalizado o sido anulados.'
        )
        return redirect('deportes:gestionar_eventos')

    # =========================================================
    # REGLA 2: No deben existir apuestas "PENDIENTES" de pago
    # =========================================================
    apuestas_pendientes = Apuesta.objects.filter(evento=evento, estado='PENDIENTE')
    
    if apuestas_pendientes.exists():
        cantidad = apuestas_pendientes.count()
        messages.error(
            request, 
            f'⚖️ DENEGADO: Este partido tiene {cantidad} apuesta(s) pendiente(s) de liquidación. '
            'Debes liquidar todas las apuestas (marcarlas como Ganadas o Perdidas) antes de borrar el evento.'
        )
        return redirect('deportes:gestionar_eventos')

    # =========================================================
    # EJECUCIÓN: Si pasa las reglas, se elimina de forma segura
    # =========================================================
    try:
        # 1. Borramos el historial de tickets para evitar el ProtectedError
        Apuesta.objects.filter(evento=evento).delete()
        
        # 2. Borramos el evento
        evento.delete()
        
        messages.success(
            request, 
            f'✅ ÉXITO: El partido "{evento.equipo_local} vs {evento.equipo_visitante}" '
            'y su historial liquidado han sido eliminados del sistema.'
        )
    except Exception as e:
        messages.error(request, f'❌ Ocurrió un error en el servidor: {str(e)}')
        
    return redirect('deportes:gestionar_eventos')