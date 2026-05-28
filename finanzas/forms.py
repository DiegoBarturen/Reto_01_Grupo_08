from datetime import date
import re
from decimal import Decimal
from django import forms
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm, UserCreationForm
from django.contrib.auth.models import User

METODO_CHOICES = [
    ('TARJETA', 'Tarjeta de Crédito/Débito'),
    ('TRANSFERENCIA', 'Transferencia Bancaria'),
]

class RegistroUsuarioForm(UserCreationForm):
    email = forms.EmailField(required=True, label="Correo electrónico")
    first_name = forms.CharField(max_length=150, required=True, label="Nombre")
    last_name = forms.CharField(max_length=150, required=False, label="Apellido")
    
    dni = forms.CharField(
        max_length=9, 
        min_length=9, 
        required=True, 
        label="DNI (8 dígitos + dígito verificador)",
        help_text="Ingresa los 9 números de tu DNI."
    )
    
    fecha_nacimiento = forms.DateField(
        required=True, 
        label="Fecha de Nacimiento",
        widget=forms.DateInput(attrs={'type': 'date'}),
        help_text="Debes ser mayor de 18 años para registrarte."
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "first_name", "last_name", "email")
        labels = {
            "username": "Nombre de usuario",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].help_text = "Usa un nombre único para identificar tu cuenta."
        self.fields["password1"].label = "Contraseña"
        self.fields["password2"].label = "Confirmar contraseña"

    def clean_fecha_nacimiento(self):
        fecha_nac = self.cleaned_data.get('fecha_nacimiento')
        if fecha_nac:
            hoy = date.today()
            edad = hoy.year - fecha_nac.year - ((hoy.month, hoy.day) < (fecha_nac.month, fecha_nac.day))
            if edad < 18:
                raise forms.ValidationError("Acceso denegado: Debes ser mayor de 18 años para operar.")
        return fecha_nac

    def clean_dni(self):
        dni_input = self.cleaned_data.get('dni')
        
        if not dni_input.isdigit() or len(dni_input) != 9:
            raise forms.ValidationError("El DNI debe contener exactamente 9 números.")
            
        parte_dni = dni_input[:8]
        digito_ingresado = int(dni_input[8])
        
        multiplicadores = [3, 2, 7, 6, 5, 4, 3, 2]
        suma = sum(int(parte_dni[i]) * multiplicadores[i] for i in range(8))
        resto = suma % 11
        
        equivalencias = [6, 7, 8, 9, 0, 1, 1, 2, 3, 4, 5]
        esperado = equivalencias[resto]
        
        if digito_ingresado != esperado:
            print(f"DEBUG: El sistema esperaba '{esperado}' para el DNI '{parte_dni}', pero ingresaste '{digito_ingresado}'. Registro permitido.")
            
        return dni_input

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        user.first_name = self.cleaned_data["first_name"]
        user.last_name = self.cleaned_data["last_name"]
        if commit:
            user.save()
        return user


class LoginUsuarioForm(AuthenticationForm):
    username = forms.CharField(label="Nombre de usuario")
    password = forms.CharField(label="Contraseña", widget=forms.PasswordInput)

    error_messages = {
        "invalid_login": "Usuario o contraseña incorrectos. Intenta nuevamente.",
    }


class PerfilUsuarioForm(forms.ModelForm):
    email = forms.EmailField(required=True, label="Correo electrónico")
    first_name = forms.CharField(max_length=150, required=True, label="Nombre")
    last_name = forms.CharField(max_length=150, required=False, label="Apellido")

    class Meta:
        model = User
        fields = ("username", "first_name", "last_name", "email")

    def clean_email(self):
        email = self.cleaned_data["email"]
        queryset = User.objects.filter(email__iexact=email).exclude(pk=self.instance.pk)
        if queryset.exists():
            raise forms.ValidationError("Ya existe una cuenta registrada con este correo.")
        return email


class RecargaSaldoForm(forms.Form):
    metodo = forms.ChoiceField(choices=METODO_CHOICES, label="Método de depósito", widget=forms.RadioSelect, initial='TARJETA')
    monto = forms.DecimalField(
        max_digits=18, decimal_places=4, min_value=Decimal("1.0000"),
        initial=Decimal("50.0000"), label="Monto a recargar"
    )

class RetiroSaldoForm(forms.Form):
    metodo = forms.ChoiceField(choices=METODO_CHOICES, label="Método de retiro", widget=forms.RadioSelect, initial='TRANSFERENCIA')
    monto = forms.DecimalField(
        max_digits=18, decimal_places=4, min_value=Decimal("50.0000"),
        initial=Decimal("50.0000"), label="Monto a retirar"
    )