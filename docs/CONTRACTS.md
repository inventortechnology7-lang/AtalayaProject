# Contratos conservados

Fuente: receptor.py, sync.py, ordenes.py y puente_pantalla.py del archivo original.

## TCP Katana :8300
UTF-8, una línea por mensaje, máximo 64 KiB. Primera línea `TOKEN <secreto>`;
rechazo cierra conexión. Respuesta `HORA <epoch segundos>`, `SYNC` cada 15 segundos.
Mensajes JSON: cfg.cor (sistemas), st.al (tuplas índice/severidad/ack/t/detalle),
st.pue (A/B), st.puerta, st.el, st.up, logs (tuplas t/sev/sistema/mensaje),
log (objeto t/v/s/m), m (tuplas sistema/magnitud/valor/unidad).
Pantalla solo para orígenes configurados; `EL 30..32` puerta A, `EL 33..35` B.
Órdenes físicas permitidas: `ORDEN`, `REINICIO` más salto de línea.
Socket Unix: `ORDEN <A|B> <ORDEN|REINICIO> <app|web> [id]`, respuesta OK/NO.
La identidad original del nodo es IP. No introducir IDs obligatorios en firmware.

## HTTP Negra
- POST /api/login: {correo,clave} -> {token}; Authorization: Bearer token.
- POST /api/sync/lote: {condominioId,alarmas,logs,muestras}.
  Alarmas: uid a-*, sistema,severidad,detalle,estado,creada,cerradaEn.
  Logs: uid l-*,t,severidad,sistema,mensaje.
  Muestras: uid m-*,sistema,magnitud,valor,unidad,tomada.
  Misma alarma actualiza estado; mismo log/muestra no duplica.
- POST /api/sync/latido: {condominioId}.
- POST /api/sync/pantalla: {condominioId,cfg?,st?}; GET /api/placa/{id}.
- GET /api/eventos: SSE `data: {"tipo":"comandos","condominioId":1}`.
- POST /api/sync/comandos?condominioId=1 -> lista de
  {id,destino,accion,linea,origen}; consumo marca entregadas en servidor.

Solo HTTP 200 confirma lote. 400 separa registro inválido, 401 renueva login,
429/5xx mantienen cola con reintento 2..60 s. Pantalla se reenvía al reconectar.
El contrato original de comandos carece de ACK físico: entregar por TCP no prueba
movimiento, y la ventana entre consumo HTTP y persistencia local puede perder una
orden. No se debe prometer exactamente una ejecución ni reintentar órdenes antiguas.
