# Katana Local: auditoría y puerta de salida

Base: main 092a8ce (PR #2), 2026-11-08. Cuenta CLI verificada:
inventortechnology7-lang. La carpeta no seguida AtalayaProjectLaptop/ no pertenece
al cambio. No se deben tocar los contenedores del proyecto hermano `atalaya`.

## Paridad obligatoria antes de retirar originales

| Fuente | Función local que se conserva | Dependencia que se retira tras validar |
|---|---|---|
| edge/ui.py | Identidad Inventor Technology / Las Palmas, puertas A/B, sistemas, nodos, alarmas activas/cerradas, logs y últimas mediciones | pendientes/último envío y órdenes remotas |
| edge/auth.py | Usuarios admin/tecnico/operador, activación, auditoría de accesos, bloqueo 5 fallos/300 s | SQLite y sesiones en memoria; scrypt requiere migración segura |
| edge/receptor.py | TCP, persistencia, alarmas, estados, telemetría, vigilancia offline, pantalla local | outbox, socket de órdenes remotas |
| edge/ordenes.py | Sólo conservar registros históricos como evidencia | Todo el consumidor SSE/HTTP y entrega de comandos centrales |
| edge/sync.py | Ningún servicio operativo local; conversión temporal sirve como referencia | login central, lotes HTTP, heartbeat, pantalla y reintentos |
| edge/puente_pantalla.py | Adaptador Serial mínimo, filtros, reconexión, RED 2/3, HORA/SYNC/EL | Ninguna lógica de negocio en este adaptador |
| backend actual | Conceptos de seguridad, paginación y auditoría reutilizables | account condo/EDGE, edge_state, sync, commands, push externo, multicliente |
| web/mobile actuales | Componentes visuales y caché revisables | Centro de operación, demo, maniobras, condominio, push Expo externo |

## Contrato observado (no inferido del hardware)

TCP 8300; primera línea `TOKEN <secreto>` antes de 10 s; comparación constante.
Máximo 64 KiB por línea JSON; HORA epoch segundos al autenticar; SYNC cada 15 s;
120 s sin línea cierra conexión. Identidad = IP remota, no puerto efímero.
`cfg.cor` enumera sistemas. `st.pue` identifica A/B; `st.puerta` es el texto
reportado; `st.el` contiene Sensor 1/2/Motor (0/1); `st.up` es dato reportado.
`st.al`: [índice sistema, severidad, reconocido, tiempo, detalle]; snapshot
completo por nodo, ausentes se cierran. `logs`: [t, sev, sistema, mensaje];
`log`: {t,v,s,m}; `m`: [sistema,magnitud,valor,unidad]. No existe UID de muestra
aportado por firmware: no se puede deduplicar una retransmisión de telemetría
sin confundir dos mediciones legítimas. Preservar UID histórico al importar.

Pantalla: origen configurable (antes localhost); EL 30/31/32 = A y 33/34/35 = B.
El protocolo sólo admite 0/1: no tiene un tercer estado desconocido. La web debe
mostrar sin comunicación y no afirmar que fallaron los tres elementos. Resolver
la compatibilidad de la señal de pantalla explícitamente antes del reemplazo.
El receptor original refresca último contacto incluso ante JSON inválido: no
reproducir esa debilidad como garantía de datos válidos.

## Datos e historial

SQLite operativo: nodos, alarmas, logs, muestras, puertas, pantalla, outbox;
usuarios.db: usuarios y accesos. Tablas opcionales ordenes_web/aplicativo son
evidencia histórica; jamás importarlas como trabajo pendiente. PostgreSQL previo
es central (telemetry JSONB, projections, commands y cuentas diferentes).
No reutilizar su volumen para un esquema nuevo incompatible.

Backups: scripts/backup-katana.py usa SQLite backup API (incluye WAL), integrity_check,
conteos y SHA256; pg_dump custom y validación pg_restore --list. Los backups
incluyen datos sensibles y se guardan fuera de Git con permisos restrictivos.
Una lista de archivo válida no equivale a una restauración probada: exigir ensayo
de restauración separado antes del corte. No eliminar originales ni volúmenes.

## Evidencia y límites

Pruebas originales: edge/test_{puertas,pantalla,puente_pantalla,reliability,v2}.py;
backend ContractTest y V2Test, scripts/smoke-stack.py; Playwright web.
Firmware disponible: únicamente protocol_probe (diagnóstico, sin GPIO/relés).
No están los sketches operativos de ESP32/puertas/Minima. Sin pruebas físicas
no se habilitan ORDEN ni REINICIO, ni se promete confirmación de actuación.

La eliminación queda condicionada a receptor Java + importación idempotente +
clientes + PostgreSQL real + pruebas TCP/USB + persistencia/offline verificadas.
