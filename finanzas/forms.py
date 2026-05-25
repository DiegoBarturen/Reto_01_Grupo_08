from decimal import Decimal

from django import forms
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm, UserCreationForm
from django.contrib.auth.models import User

from .models import Transaccion


class RegistroUsuarioForm(UserCreationForm):
    email = forms.EmailField(required=True, label="Correo electronico")
    first_name = forms.CharField(max_length=150, required=True, label="Nombre")
    last_name = forms.CharField(max_length=150, required=False, label="Apellido")

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "first_name", "last_name", "email")
        labels = {
            "username": "Nombre de usuario",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].help_text = "Usa un nombre unico para identificar tu cuenta."
        self.fields["password1"].label = "Contrasena"
        self.fields["password1"].help_text = ""
        self.fields["password2"].label = "Confirmar contrasena"
        self.fields["password2"].help_text = "Repite la contrasena para confirmar el registro."

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
    password = forms.CharField(label="Contrasena", widget=forms.PasswordInput)

    error_messages = {
        "invalid_login": "Usuario o contrasena incorrectos. Intenta nuevamente.",
        "inactive": "Esta cuenta se encuentra inactiva.",
    }


class PerfilUsuarioForm(forms.ModelForm):
    email = forms.EmailField(required=True, label="Correo electronico")
    first_name = forms.CharField(max_length=150, required=True, label="Nombre")
    last_name = forms.CharField(max_length=150, required=False, label="Apellido")

    class Meta:
        model = User
        fields = ("username", "first_name", "last_name", "email")
        labels = {
            "username": "Nombre de usuario",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].help_text = "Este nombre se mostrara como identificador principal de tu cuenta."

    def clean_email(self):
        email = self.cleaned_data["email"]
        queryset = User.objects.filter(email__iexact=email).exclude(pk=self.instance.pk)
        if queryset.exists():
            raise forms.ValidationError("Ya existe una cuenta registrada con este correo.")
        return email


class CambioContrasenaPerfilForm(PasswordChangeForm):
    old_password = forms.CharField(label="Contrasena actual", widget=forms.PasswordInput)
    new_password1 = forms.CharField(label="Nueva contrasena", widget=forms.PasswordInput)
    new_password2 = forms.CharField(label="Confirmar nueva contrasena", widget=forms.PasswordInput)

    error_messages = {
        "password_incorrect": "La contrasena actual no es correcta.",
        "password_mismatch": "Las nuevas contrasenas no coinciden.",
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["new_password1"].help_text = ""
        self.fields["new_password2"].help_text = "Vuelve a escribir la nueva contrasena para confirmar el cambio."


class RecargaSaldoForm(forms.Form):
    metodo = forms.ChoiceField(
        choices=Transaccion.Metodo.choices,
        label="Metodo de deposito",
        widget=forms.RadioSelect,
        initial=Transaccion.Metodo.TARJETA,
    )
    monto = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        min_value=Decimal("1.00"),
        initial=Decimal("50.00"),
        label="Monto a recargar",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["monto"].widget.attrs.update(
            {
                "placeholder": "Ej. 50.00",
                "step": "0.01",
            }
        )


class RetiroSaldoForm(forms.Form):
    metodo = forms.ChoiceField(
        choices=Transaccion.Metodo.choices,
        label="Metodo de retiro",
        widget=forms.RadioSelect,
        initial=Transaccion.Metodo.TRANSFERENCIA,
    )
    monto = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        min_value=Decimal("50.00"),
        initial=Decimal("50.00"),
        label="Monto a retirar",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["monto"].widget.attrs.update(
            {
                "placeholder": "Ej. 50.00",
                "step": "0.01",
            }
        )
