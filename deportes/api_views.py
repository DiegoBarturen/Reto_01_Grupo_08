from django.db import transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAdminUser
from rest_framework.response import Response
from .models import Evento
from .serializers import CuotaSerializer, EventoCarteleraSerializer, EventoSerializer


def _eventos_apostables_queryset():
    return (
        Evento.objects.filter(estado="PENDIENTE", fecha_hora__gt=timezone.now())
        .select_related("cuotas")
        .order_by("fecha_hora")
    )


@api_view(["GET"])
@permission_classes([AllowAny])
def api_listar_eventos(request):
    eventos = _eventos_apostables_queryset()

    deporte = request.query_params.get("deporte")
    if deporte:
        eventos = eventos.filter(deporte=deporte.upper())

    serializer = EventoCarteleraSerializer(eventos, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(["GET"])
@permission_classes([AllowAny])
def api_detalle_evento(request, evento_id):
    try:
        evento = Evento.objects.select_related("cuotas").get(pk=evento_id)
    except Evento.DoesNotExist:
        return Response(
            {"detail": "Evento deportivo no encontrado."},
            status=status.HTTP_404_NOT_FOUND,
        )

    serializer = EventoSerializer(evento)
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(["POST"])
@permission_classes([IsAdminUser])
def api_crear_evento(request):
    serializer = EventoSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    with transaction.atomic():
        evento = serializer.save()

    return Response(EventoSerializer(evento).data, status=status.HTTP_201_CREATED)


@api_view(["PATCH"])
@permission_classes([IsAdminUser])
def api_actualizar_evento(request, evento_id):
    try:
        evento = Evento.objects.select_related("cuotas").get(pk=evento_id)
    except Evento.DoesNotExist:
        return Response(
            {"detail": "Evento deportivo no encontrado."},
            status=status.HTTP_404_NOT_FOUND,
        )

    serializer = EventoSerializer(evento, data=request.data, partial=True)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    with transaction.atomic():
        evento = serializer.save()

    return Response(EventoSerializer(evento).data, status=status.HTTP_200_OK)


@api_view(["PATCH"])
@permission_classes([IsAdminUser])
def api_actualizar_cuotas(request, evento_id):
    try:
        evento = Evento.objects.select_related("cuotas").get(pk=evento_id)
    except Evento.DoesNotExist:
        return Response(
            {"detail": "Evento deportivo no encontrado."},
            status=status.HTTP_404_NOT_FOUND,
        )

    cuota = getattr(evento, "cuotas", None)
    serializer = CuotaSerializer(cuota, data=request.data, partial=True)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    with transaction.atomic():
        serializer.save(evento=evento)

    return Response(EventoSerializer(evento).data, status=status.HTTP_200_OK)
