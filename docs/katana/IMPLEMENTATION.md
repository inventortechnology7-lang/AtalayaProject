# Katana Local: implementación y evidencia

## Arquitectura activa

Spring Boot 3.5 / Java 21 es el único backend. `BoardTcpServer` usa sockets con
hilos virtuales, autenticación TOKEN, límites de tamaño, deadline por frame y
UUID por conexión. `PersistentBoardSink` guarda cfg/st/logs/log/m en transacciones
PostgreSQL. Una conexión sustituida no puede escribir ni desconectar la nueva.
Flyway aplica exclusivamente `db/katana`. Spring Data JPA administra usuarios;
JdbcTemplate implementa consultas históricas y transacciones de recepción.

React/TypeScript, Router y Tailwind proporcionan ocho vistas: resumen, puertas,
nodos, alarmas, registros, historial, telemetría y usuarios/configuración. React
Native comparte el contrato `/api/local`. Ningún cliente consulta servicios centrales.
Los clientes muestran datos de PostgreSQL, nunca rellenan dispositivos inexistentes.

## Paridad de funciones locales

| Función anterior | Equivalente y comprobación |
| --- | --- |
| auth: usuarios, roles, bloqueo, accesos | UserService, AuthService, BCrypt, sesiones revocables y audit_logs; JUnit RBAC y recuperación |
| ui: acceso y estado local | React, `/auth`, `/dashboard`, `/doors`; Playwright con API real |
| receptor: TOKEN, HORA, SYNC | BoardTcpServerTest: token inválido, reconexión, deadline, tamaño y frames inválidos |
| cfg, st, logs, log, m | PersistentBoardSink; JUnit PostgreSQL y smoke-local |
| puertas A/B, sensores, desconexiones | DoorService y MonitoringService; se conservan observaciones y se indica indisponibilidad |
| alarmas activas/cerradas/reconocidas | AlarmService; historial y reconocimiento local auditado |
| EL 30–35 y USB | screenOrigins + DoorService + adaptador USB; prueba de protocolo con simulador |
| registros, filtros, paginación | Queries y RecordsController; parámetros SQL y límites de consulta |
| estado en vivo | SSE después del commit; reconexión y consulta completa al conectar |
| SQLite histórico | backup-katana/import-katana; UID, checksums, rollback e importación repetida |

Las órdenes remotas y la sincronización central se retiran expresamente. No existe
API de movimiento ni se envían ORDEN/REINICIO. Esto no certifica maniobras físicas.
El protocolo m carece de UID/fecha: cada recepción es una muestra nueva; no se
eliminan muestras iguales que podrían ser mediciones legítimas. Logs y alarmas
conservan identidad determinista; repetir un estado no duplica eventos de puerta.
SSE invalida consultas: no pretende reproducir un diario durable por Last-Event-ID;
el historial completo permanece en PostgreSQL y se vuelve a consultar tras reconectar.

## Validación de esta continuación

- JUnit con PostgreSQL 17 real: transporte, integración HTTP/TCP, RBAC,
  autenticación, estados A/B, rollback de frame inválido y recuperación auditada.
- Migración sintética: fallo transaccional, checksum alterado, Unicode,
  preservación de órdenes como evidencia no ejecutable y repetición idempotente.
- Respaldo real `20261108T192802Z`: 1 nodo de origen, 2 puertas, 5 alarmas,
  27 logs, 0 muestras, 1 usuario y 12 accesos; 99 registros originales archivados.
  Una segunda identidad histórica existe por referencias de logs, no por hardware nuevo.
- 27 pruebas Python anteriores pasaron antes de retirar el servidor sustituido.
- Expo exporta bundles Android/iOS y comprueba TypeScript estricto. Esto no equivale
  a un APK/IPA firmado ni a probar un teléfono físico.

El verificador anterior fallaba al conectar a localhost en una red Docker
`internal` que no publicaba puertos. `verify-stack.py` usa las IP de ese puente en
Linux, conserva el volumen de prueba y ejecuta secuencialmente reinicio y Playwright.
Nunca se debe ejecutar otro simulador mientras compara persistencia.

## Límites de la evidencia

No se usó hardware físico, USB real, emuladores móviles ni comandos de movimiento.
Los sketches operativos de puertas y pantalla no están en este repositorio;
se conserva el adaptador USB y el cliente de diagnóstico sin GPIO.
Las imágenes y dependencias necesitan descargarse durante la preparación/build;
la ejecución con imágenes ya construidas funciona sin WAN. El móvil requiere LAN
(o una VPN gestionada externamente); no hay push fuera de la red ni en segundo plano.
La red `internal` de ensayo prueba el aislamiento del stack, no una desconexión física
de la laptop. Los resultados CI deben comprobarse en el PR para el commit exacto.

## Corte realizado en la laptop (2026-11-08, hora de Lima)

- Respaldo final con escritor detenido: `backups/20261109T011208Z` (UTC).
  Se ensayó su restauración e importación repetida antes de activar el receptor.
- Flyway `--migrate-only` preparó `katana-local_katana-data`; se importó dos veces
  sin cambios y se recuperó el ADMIN histórico con una contraseña nueva en `.env`.
  `RECOVER_IMPORTED_ADMIN` volvió a false tras verificar el acceso.
- `atalaya-laptop-edge-1`, backend, web y PostgreSQL anteriores están detenidos;
  sus contenedores y volúmenes se conservaron. No se tocaron otros proyectos Docker.
- El proyecto final tiene tres servicios saludables: web 28082, API 28080 y TCP
  Java 8300, enlazados a localhost. La base final contiene 27 logs, 5 alarmas,
  2 puertas, 1 usuario y 99 registros históricos originales; cero nodos simulados
  conectados. Las pruebas con simuladores usan exclusivamente `katana-verify`.
- Dump de Katana actual restaurado en PostgreSQL aislado: SHA256 válido y hashes
  completos de filas idénticos en 11 tablas, incluidos usuarios y auditoría.
- Resultado local final: 7 tests TCP, 2 tests de integración con PostgreSQL,
  7 tests USB, migración sintética y real, dos Playwright (1440/390) y exportación
  Expo Android/iOS aprobados. SSE se comprueba recibiendo una revisión posterior
  al commit, además del evento inicial y reconexión de los clientes.
- La copia anidada `AtalayaProjectLaptop/` se conserva sin modificar y se excluye
  sólo del índice del repositorio padre mediante `.git/info/exclude`.
- Fuentes retiradas y configuración anterior conservadas privadamente en
  `backups/retired-source-20261109`; no forman parte de la aplicación final.

La comprobación de secretos se refiere al árbol versionado final y patrones
conocidos, no a una certificación absoluta ni al borrado del historial Git.
El PR hacia main es #4; no se ha realizado merge. Consultar sus checks para
el resultado remoto del commit final.
