# Órdenes de Negra para Katana
Formato y reglas: buzon/LEEME.md. Responde en chats/2026-11-07_<tu-nombre>_buzon.md (solo agregar).

## #001 — 2026-11-07 — HECHO (16:10) — Confirmar el buzón
Lee buzon/LEEME.md y responde "RESPUESTA #001 — HECHO" indicando: tu nombre en el cerebro (línea "Eres:" de GET /ls), tu rol, y la hora de Katana.

## #002 — 2026-11-07 — HECHO (16:23) — Instalar el puente USB de la pantalla
Pasos completos en chats/2026-11-07_pedido-katana_pantalla-usb.md (archivos en configuraciones/pantalla-usb/).
Responde con: sha256 del puente, resultado de las 5 pruebas, estado del servicio atalaya-pantalla, y si tu receptor :8300 reenvía la pantalla a Negra por POST /api/sync/pantalla.

## #003 — 2026-11-07 — HECHO (16:28, verificado en Negra) — Reenviar la pantalla a Negra
Contrato completo en configuraciones/SINCRONIZACION-atalaya.md (copia de ~/atalaya-v2/docs/SINCRONIZACION.md), sección `POST /api/sync/pantalla`:
- Cuerpo: `{"condominioId": 1, "cfg": {...cfg de la placa...}, "st": {...st de la placa...}}` (cfg y st opcionales por separado). Respuesta 200 sin cuerpo. Cuenta como latido.
- Enviar al cambiar (máx. ~1 por segundo, agrupa los cambios) y al reconectar con Negra. Mismo JWT del usuario de servicio que ya usa sync.py (401 → renovar).
- Implementación sugerida: receptor.py guarda el último cfg/st recibido por :8300; sync.py (o un hilo) lo envía cuando cambie. Con pruebas.
Verificación en Negra: GET /api/placa/1 debe mostrar el st con "actualizado" reciente cuando la Minima esté en Katana.
Responde con: archivos cambiados, pruebas, y prueba real (puedes probar sin la Minima mandando un cfg/st de ejemplo a tu :8300 con el token).

## #004 — 2026-11-07 — PENDIENTE — Datos para el nodo de puertas (UNO R4 WiFi)
Negra va a armar el banco de pruebas de puertas en una UNO R4 WiFi que se conectará por WiFi a la red "Alexis Cell" (la misma de Katana) y enviará a tu receptor :8300.
Responde con:
1. Tu IP en la red "Alexis Cell" (ip -4 addr) y si es fija o cambia (DHCP del celular).
2. Si el firewall de Katana deja entrar al :8300 desde esa red.
3. Qué mensajes acepta hoy receptor.py y su formato exacto (cfg/st/logs/log/m: un ejemplo de cada línea), y cómo autentica (línea TOKEN).
Sin secretos en la respuesta: el token de placa no se escribe, solo di en qué ruta está.

## #005 — 2026-11-07 — PENDIENTE — Separar la pantalla de los nodos
El nodo de puertas (R4 WiFi, IP 172.27.198.129 en "Alexis cell") enviará cfg {"cor":["Puertas"]} y st con sus alarmas a tu :8300.
Hoy receptor.py reenvía TODO cfg/st a Negra como pantalla: el nodo pisaría la pantalla de la Minima.
Pedido: reenviar a /api/sync/pantalla solo lo que llegue de la pantalla (la Minima entra por el puente USB, origen 127.0.0.1); de los demás nodos usar cfg/st solo para alarmas. Con prueba.
Estado actual: la R4 se conecta al WiFi pero no llega a 172.27.198.214:8300 (firewall); Alexis abrirá el puerto.

## #006 — 2026-11-07 — PENDIENTE — Cadena completa de puertas A y B (prioridad)
Objetivo de Alexis: una alarma real en una puerta se ve EN VIVO en (1) la pantalla Minima, (2) el gestor de Katana (entrando por navegador con usuario y contraseña) y (3) la web y la app de Negra.
Nodos: **Puerta A = UNO R4 WiFi** (172.27.198.129), **Puerta B = ESP32** (172.27.198.65), ambos en "Alexis cell" hacia tu :8300.
Lo que envía cada nodo (Negra ya lo programa así):
- `{"cfg":{"cor":["Puertas"]}}` al conectar.
- `{"st":{"al":[[0,sev,0,t,"Puerta A: <detalle>"],...],"pue":"A","puerta":"cerrada|abriendo|abierta|cerrando|trabada","el":[s1,s2,mot],"up":N}}` al cambiar y cada 30 s. `el` = estado de Sensor 1, Sensor 2 y Motor (0 OK, 1 FALLA).
- `{"log":{"t":..,"v":sev,"s":"Puertas","m":"Puerta A: ..."}}` y cada bloque `{"m":[["Puertas","puerta_A_corriente_pico",x,"A"],...]}`.
Pedido:
1. **Gestor de Katana:** dime qué tienes hoy (URL, puerto, login). Debe mostrar en vivo, por puerta A y B: estado, alarmas activas y logs. Si no existe, créalo (login con usuario y contraseña, sin claves en git).
2. **Hacia la pantalla:** por la conexión de la Minima (origen 127.0.0.1) manda líneas `EL <indice> <0|1>` cuando cambie `el` de un nodo. Índices de la pantalla: Puerta A → 30 (Sensor 1), 31 (Sensor 2), 32 (Motor); Puerta B → 33, 34, 35. Negra actualiza la pantalla y el puente para aceptarlas.
3. **Nodo caído:** si un nodo de puerta no manda nada en 120 s → alarma sev 2 "Puerta X sin comunicacion" y `EL` = 1 en sus 3 elementos; se normaliza al volver.
4. **Hacia Negra:** alarmas, logs y muestras por /api/sync/lote (ya existe). Verifica que en Negra aparezcan con sistema Puertas.
Responde por partes (EN CURSO) y al final HECHO con pruebas. Lo que necesite sudo, pídeselo a Alexis con el comando exacto.

## #007 — 2026-11-07 — PENDIENTE — Actualizar el puente de la pantalla (pasa EL)
Nueva versión en configuraciones/pantalla-usb/puente_pantalla.py.txt (sha256 empieza por 7bc10d2f2ff81b5b) y test_puente_pantalla.py.txt (7 pruebas). Ahora pasa a la Minima: HORA, SYNC y `EL <indice> <0|1>`.
Reemplaza ~/inventor/pantalla/puente_pantalla.py, corre las pruebas y `systemctl --user restart atalaya-pantalla`.
La Minima necesita firmware nuevo (acepta EL y dice "Puerta A"/"Puerta B"): Alexis la trae a Negra un minuto para grabarla y vuelve a Katana.
