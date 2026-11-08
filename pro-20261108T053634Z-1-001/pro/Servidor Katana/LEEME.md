# Katana — servidor local Condominio Las Palmas (Inventor Technology / Proyecto Atalaya)

Nodos (ESP32/R4) --TCP :8300--> Katana (SQLite + outbox) --HTTP/Tailscale--> Negra (100.101.225.120)

## Piezas
| Archivo | Qué hace | Servicio |
|---|---|---|
| receptor.py | TCP :8300, protocolo placa (TOKEN, cfg/st/logs/log/m), guarda en katana.db + outbox | `katana-receptor` (sistema) |
| ui.py | Web local solo lectura :8080 (sin login) | `katana-ui` (usuario) |
| sync.py | Sube el outbox a Negra por lotes + latido cada 30 s | `katana-sync` (usuario) |
| nodo_simulado.py / mock_negra.py | Solo pruebas | — |

Config en `.env` (permisos 600, ignorado por git): PLACA_TOKEN, NEGRA_URL, SYNC_USUARIO, SYNC_CLAVE, CONDOMINIO_ID, CONDOMINIO.
Scripts: instalar-servicio.sh (sudo), instalar-ui.sh, instalar-sync.sh, poner-clave.sh.

## Contrato con Negra (doc completo en Negra: ~/atalaya-v2/docs/SINCRONIZACION.md)
Login `POST /api/login {correo,clave}`; `POST /api/sync/latido`; `POST /api/sync/lote` (alarmas/logs/muestras, idempotente por uid).
Solo se marca enviado lo que Negra respondió 200; 400 aparta el registro (enviado=-1); 401 renueva token; 429/5xx reintenta 2..60 s.

## Probado (2026-11-05)
- Receptor: token malo se cierra, JSON roto se ignora, datos guardados (nodo simulado).
- Sync contra Negra real: lote 5 nuevos; reenvío 5 duplicados; sin latido ~103 s -> perdida_gestion; reanudar -> se quita sola.
- Sin internet acumula y al volver sube todo sin duplicar (simulador, 455 regs).
## NO probado
- Nodos reales (ESP32/R4), varios nodos a la vez, líneas >64 KB reales, reinicio del equipo con todo en marcha.
- Firewall: ufw inactivo (no se abrió nada). IP de Katana por DHCP: reservar 192.168.100.14 en el router.
- La web local no tiene login. Nombre de nodo = IP de origen (puede duplicarse si cambia la IP).
