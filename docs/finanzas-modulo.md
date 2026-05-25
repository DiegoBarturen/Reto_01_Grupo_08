# Modulo Finanzas

Este modulo ya tiene una interfaz funcional y una base API para evitar cambios desordenados mientras el equipo integra el resto de la plataforma.

## Pantallas activas

- `/registro/`: alta de usuario con validacion de contrasena en vivo
- `/login/`: acceso a la cuenta
- `/billetera/`: panel principal con saldo e historial
- `/billetera/recarga/`: flujo de recarga
- `/billetera/retiro/`: flujo de retiro
- `/billetera/transacciones/<id>/`: detalle de cada movimiento
- descarga PDF individual desde el detalle del movimiento
- descarga PDF grupal desde el historial seleccionando varios movimientos
- `/perfil/`: configuracion de cuenta

## Endpoints API listos

- `GET /api/billetera/`: devuelve saldo, datos del usuario y total de movimientos
- `GET /api/transacciones/`: devuelve el historial de transacciones del usuario autenticado
- `POST /api/recargas/`: registra una recarga con `metodo` y `monto`
- `POST /api/retiros/`: registra un retiro con `metodo` y `monto`

## Contrato visual del modulo

- Mantener el layout premium oscuro ya implementado en `finanzas/templates/finanzas/`
- No mezclar CSS dentro del HTML; usar `finanzas/static/finanzas/styles.css`
- La pantalla `billetera` es un resumen, no el formulario principal de recarga
- La recarga y el retiro ocurren en vistas separadas para no saturar el panel principal
- Cada transaccion debe conservar su vista de detalle
- El historial ya soporta seleccion multiple para exportar PDF; no reemplazarlo por acciones masivas confusas

## Modelos actualmente usados

- `User` de Django como usuario base
- `Billetera` para saldo y relacion con el usuario
- `Transaccion` para movimientos de recarga y retiro
- `Auditoria` para trazabilidad de acciones relevantes

## Nota para integracion futura

Si otro modulo consume finanzas, preferir primero los endpoints API antes de reemplazar las pantallas HTML existentes.
