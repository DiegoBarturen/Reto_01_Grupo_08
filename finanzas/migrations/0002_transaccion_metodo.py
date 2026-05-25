from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("finanzas", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="transaccion",
            name="metodo",
            field=models.CharField(
                choices=[
                    ("TARJETA", "Tarjeta virtual"),
                    ("TRANSFERENCIA", "Transferencia simulada"),
                    ("YAPE_PLIN", "Yape o Plin simulado"),
                ],
                default="TARJETA",
                max_length=20,
            ),
        ),
    ]
