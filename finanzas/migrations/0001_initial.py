import decimal

import django.core.validators
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Auditoria",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("accion", models.CharField(max_length=100)),
                ("detalle", models.TextField()),
                ("creado_en", models.DateTimeField(auto_now_add=True)),
                (
                    "usuario",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="auditorias",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Auditoria",
                "verbose_name_plural": "Auditorias",
                "ordering": ["-creado_en"],
            },
        ),
        migrations.CreateModel(
            name="Billetera",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "saldo",
                    models.DecimalField(
                        decimal_places=2,
                        default=decimal.Decimal("0.00"),
                        max_digits=10,
                        validators=[django.core.validators.MinValueValidator(decimal.Decimal("0.00"))],
                    ),
                ),
                ("actualizado_en", models.DateTimeField(auto_now=True)),
                ("creado_en", models.DateTimeField(auto_now_add=True)),
                (
                    "usuario",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="billetera",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Billetera",
                "verbose_name_plural": "Billeteras",
            },
        ),
        migrations.CreateModel(
            name="Transaccion",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("tipo", models.CharField(choices=[("RECARGA", "Recarga"), ("RETIRO", "Retiro")], max_length=20)),
                (
                    "monto",
                    models.DecimalField(
                        decimal_places=2,
                        max_digits=10,
                        validators=[django.core.validators.MinValueValidator(decimal.Decimal("0.01"))],
                    ),
                ),
                ("descripcion", models.CharField(blank=True, max_length=255)),
                ("creado_en", models.DateTimeField(auto_now_add=True)),
                (
                    "billetera",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="transacciones",
                        to="finanzas.billetera",
                    ),
                ),
            ],
            options={
                "verbose_name": "Transaccion",
                "verbose_name_plural": "Transacciones",
                "ordering": ["-creado_en"],
            },
        ),
    ]
