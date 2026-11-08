
## Respuesta #009 (versión SSE) — 2026-11-07 23:25 — Katana
HECHO y probado con la placa real.
1. Nuevo servicio `katana-ordenes` (ordenes.py): UNA conexión SSE a /api/eventos. Al conectar llama una vez a /api/sync/comandos y después solo cuando llega {"tipo":"comandos"}. Si se corta, reconecta con espera 1→30 s. No hay consulta periódica.
2. Cada orden se guarda primero en la tabla ordenes_aplicativo u ordenes_web, y también en las carpetas ordenes-aplicativo/ y ordenes-web/ (jsonl por día). Luego pasa al receptor por un socket local, y el receptor manda `linea\n` a la placa de esa puerta.
3. Log "Orden remota REINICIO (web) #N entregada a Puerta A" o "… no entregada …: puerta sin conexión" (sev 2). Va a Negra en el lote y se ve en el gestor (sección "Órdenes remotas").
4. Seguridad: si el receptor está caído, la orden NO se guarda para más tarde (un reinicio atrasado es peligroso). Se marca no entregada y queda en el log.
5. Prueba real 23:20: las 3 pendientes (#1 y #2 REINICIO, #3 ORDEN) se entregaron. La Puerta A registró "Reinicio remoto de la tarjeta del porton" y "Orden del servidor: pulso a la tarjeta". Llegó una 4.ª a las 23:20:28 y también se entregó.
6. BUG EN NEGRA: /api/sync/lote responde HTTP 500 si llegan 2 logs con el mismo texto en el mismo segundo, aunque el uid sea distinto (probado registro por registro). Eso bloqueó la cola unos 80 s. En Katana lo resolví agregando el número de orden (#N) al texto. Pidan a Negra que deduplique solo por uid y que, ante un duplicado, responda 200 y lo ignore, nunca 500.
7. Pendiente: mostrar las órdenes en la pantalla Minima (el puente hoy solo manda HORA/SYNC/EL; habría que acordar una línea nueva con su firmware). El receptor necesita un reinicio con sudo para usar el #N; después hay que reiniciar katana-ordenes.
