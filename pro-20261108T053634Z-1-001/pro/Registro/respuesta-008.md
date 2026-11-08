
## Respuesta #008 — 2026-11-07 22:20 — Katana
1. Katana ya está en "Alexis cell". IP sin cambio: 172.27.198.214. Puerto 8300 abierto (comprobado).
2. La Puerta A (172.27.198.129) se conectó a las 22:05:12 y envió datos hasta las 22:07:42. Luego se quedó callada y el receptor la cerró a las 22:09:42 (120 s sin datos). No ha vuelto a conectarse, aunque responde al ping (unos 100 ms).
3. Logs, alarmas y muestras (puerta_A_estado, maniobras, corriente_prom, corriente_pico, tiempo_operacion) se guardan en orden por hora. El outbox está vacío: todo se envió a Negra.
4. Alarmas abiertas: "Puerta A sin comunicacion" (22:09:44) y "Puerta trabada" (22:05:31).
5. Últimas 10 líneas de logs de la Puerta A (hay 8 en total):
17:24:25 sev0 Estado inicial entre finales
17:24:44 sev2 Reinicio de la tarjeta del porton (1/3 en la hora)
17:24:44 sev2 Puerta trabada: no llego al final de carrera
18:34:07 sev2 Puerta A sin comunicacion
22:05:12 sev0 Estado inicial entre finales
22:05:31 sev2 Reinicio de la tarjeta del porton (1/3 en la hora)
22:05:31 sev2 Puerta trabada: no llego al final de carrera
22:09:44 sev2 Puerta A sin comunicacion
6. Pendiente en el R4: deja de enviar a los ~2,5 min y no reconecta. Revisar el bucle de reconexión y el envío periódico de st (como máximo cada 60 s).
