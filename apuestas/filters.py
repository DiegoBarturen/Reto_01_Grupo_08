import django_filters
from .models import Apuesta

class ApuestaFilter(django_filters.FilterSet):
    # Búsqueda por nombre de usuario (sin importar mayúsculas)
    usuario = django_filters.CharFilter(field_name='usuario__username', lookup_expr='icontains', label='Usuario')
    # Filtro por rango de fechas
    fecha_desde = django_filters.DateFilter(field_name='evento__fecha_hora', lookup_expr='gte', label='Desde')
    fecha_hasta = django_filters.DateFilter(field_name='evento__fecha_hora', lookup_expr='lte', label='Hasta')

    class Meta:
        model = Apuesta
        fields = ['usuario', 'fecha_desde', 'fecha_hasta']