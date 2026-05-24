from django.shortcuts import render, redirect
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from .models import Evento
from .forms import EventoForm, CuotaForm

# Tu vista pública (la cartelera)
def cartelera(request):
    eventos = Evento.objects.filter(estado__in=['PENDIENTE', 'EN_JUEGO']).order_by('fecha_hora')
    return render(request, 'deportes/cartelera.html', {'eventos': eventos})

# Tu nueva vista privada (solo para administradores)
@staff_member_required(login_url='/admin/login/')
def crear_partido(request):
    if request.method == 'POST':
        evento_form = EventoForm(request.POST)
        cuota_form = CuotaForm(request.POST)
        
        if evento_form.is_valid() and cuota_form.is_valid():
            # Guardamos el partido
            evento = evento_form.save()
            # Guardamos las cuotas y las enlazamos al partido recién creado
            cuota = cuota_form.save(commit=False)
            cuota.evento = evento
            cuota.save()
            
            messages.success(request, '¡Partido y cuotas creados exitosamente!')
            return redirect('deportes:cartelera')
    else:
        evento_form = EventoForm()
        cuota_form = CuotaForm()

    return render(request, 'deportes/crear_partido.html', {
        'evento_form': evento_form,
        'cuota_form': cuota_form
    })