# Estado de implementación incremental

El adaptador `com.inventor.katana.devices.BoardTcpServer` es una base de transporte
Java 21 probada independientemente. **Todavía no sustituye el receptor operativo.**
No se registra como bean ni se abre otro puerto al arrancar el backend existente.
BoardSink define la frontera de persistencia transaccional pendiente de conectar.

- Puerto predeterminado contractual: 8300 (el constructor recibe dirección explícita).
- TOKEN, HORA, SYNC, límites, autenticación con comparación constante, identidad IP.
- 128 conexiones como límite inicial; tareas virtuales, cierre ordenado y UUID por conexión.
- JSON completo validado antes de entregar al servicio de persistencia.
- No contiene cliente remoto, comandos físicos ni reenvío diferido.
- La compatibilidad EL/pantalla, persistencia, supervisión offline y clientes siguen
  siendo requisitos para habilitarlo. No afirmar paridad por estos tests de transporte.

El esquema `db/katana/V1__katana_local.sql` está fuera de la ruta Flyway activa.
Se destina exclusivamente a una base nueva: no aplicar sobre el volumen central.
Incluye tablas relacionales requeridas; `legacy_records` preserva evidencia no
operativa y `import_runs` registra trazabilidad de importación. No existe outbox.
El importador inicial `scripts/import-katana.py` ya se verificó con el backup real y
con fixtures sintéticos sobre PostgreSQL 17 aislado. Sólo permite una pareja de
backups por base y rechaza un destino con sesiones/conexiones: no es un importador
incremental para producción activa. Se conserva cada UID y se archivan los
registros originales (sin sal/clave). Falta implementar el restablecimiento de
usuarios y la integración con el backend nuevo. Las referencias de nodo que sólo
existen en logs (por ejemplo, katana) se preservan como identidades históricas,
no como hardware nuevo detectado.

Decisión de transporte: sockets con tareas virtuales de Java 21 simplifican el
protocolo por líneas sin añadir Netty. Se mantienen límites explícitos de recursos.
Referencia: https://docs.oracle.com/en/java/javase/21/core/virtual-threads.html

## Corte y rollback (pendientes de ensayo)

1. Crear backup online con `python3 scripts/backup-katana.py`; copiarlo a almacenamiento protegido externo.
2. Restaurar el dump en PostgreSQL aislado y comprobar tablas/conteos; verificar SHA256.
3. Importar SQLite en una base Katana nueva, cotejar UIDs/conteos y repetir importación.
4. Validar TCP/USB, seguridad, clientes, reinicios y WAN desconectada.
5. Tomar backup final con escritores detenidos; repetir la importación final en otra base vacía antes de mover puertos.
6. Detener únicamente contenedores `atalaya-laptop-*` antiguos, sin `down -v` ni prune.
7. Ante fallo: detener Katana nuevo, restaurar configuración/imagen anterior y reiniciar
   contenedores con sus volúmenes conservados. Conciliar datos recibidos después del corte;
   nunca asumir rollback sin pérdida si hubo escrituras nuevas.


## Validación realizada el 2026-11-08

- 7 tests JUnit del transporte: autenticación, deadline, HORA/SYNC, todos los tipos
  de mensaje, frame inválido sin efectos parciales, tamaño máximo y reconexión.
- 27 tests originales Python aprobados (se conservan como referencia de paridad).
- Backup SQLite: integrity_check, SHA256 y conteos verificados; 1 nodo registrado,
  2 puertas, 5 alarmas, 27 logs, 0 muestras, 1 usuario, 12 accesos y 13 órdenes web.
- Dump PostgreSQL restaurado en otra base, sin montar volúmenes originales.
- Importación repetida: snapshots completos de filas idénticos, sin duplicación.
- Fixture: telemetría, Unicode/comillas, estado cerrado de alarma, rol local,
  evidencia de orden pendiente sin ejecución y rechazo de checksum alterado.
- PostgreSQL de pruebas con `--network none`: migración ejecutada sin servicios
  centrales ni conectividad externa. Esto NO certifica todavía la aplicación offline.

## Pendiente para cumplir el criterio final

Persistencia transaccional BoardSink; Spring Data JPA; dominios y APIs locales;
Security/RBAC/sesiones/restablecimientos; OpenAPI; SSE de estado; EL y puente USB;
monitoreo offline; React Router/Tailwind y ocho pantallas locales; cliente móvil;
Compose de tres servicios; reinicios/persistencia real; pruebas end-to-end y
retirada de los originales. No se ha cambiado el servicio operativo ni se ha
habilitado ningún comando físico. Esta rama aún no está lista para merge ni
para sustituir Katana en producción.
