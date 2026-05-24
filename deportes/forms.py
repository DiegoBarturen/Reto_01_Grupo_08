from django import forms
from .models import Evento, Cuota

class EventoForm(forms.ModelForm):
    class Meta:
        model = Evento
        # Aquí añadimos 'deporte' al inicio de la lista
        fields = ['deporte', 'equipo_local', 'equipo_visitante', 'fecha_hora', 'estado']
        widgets = {
            'deporte': forms.Select(attrs={'class': 'form-control'}),
            'fecha_hora': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'}),
            'equipo_local': forms.TextInput(attrs={'class': 'form-control'}),
            'equipo_visitante': forms.TextInput(attrs={'class': 'form-control'}),
            'estado': forms.Select(attrs={'class': 'form-control'}),
        }

class CuotaForm(forms.ModelForm):
    class Meta:
        model = Cuota
        fields = ['paga_local', 'paga_empate', 'paga_visitante']
        widgets = {
            'paga_local': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'paga_empate': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'paga_visitante': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
        }