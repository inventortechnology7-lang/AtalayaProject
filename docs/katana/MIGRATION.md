# Migración reproducible y recuperación

Nunca aplicar el esquema local sobre PostgreSQL central ni montar sus volúmenes.
El importador exige un destino vacío sin sesiones ni conexiones y acepta sólo
la misma pareja de SQLite por base. Conserva UID, conteos y registros originales
(sin sal/clave), incluidos eventos de órdenes que nunca ejecuta.

1. Con el sistema anterior aún disponible, ejecutar `python3 scripts/backup-katana.py`.
   Copiar el directorio indicado a almacenamiento protegido externo.
2. Ensayar `python3 scripts/test-katana-migration.py --backup backups/DIRECTORIO`.
   Restaura el dump PostgreSQL en una base aislada y comprueba SQLite, conteos,
   UID y repetición íntegra de la importación.
3. Detener sólo el escritor antiguo durante el corte y tomar un respaldo final.
   Con el contenedor edge detenido, ejecutar
   `python3 scripts/backup-katana.py --stopped`: copia SQLite y WAL a un temporal
   privado y usa SQLite backup API sin modificar el volumen original. No reiniciar dos receptores en 8300.
4. Preparar `.env` y un proyecto/volumen local NUEVO. Construir las imágenes;
   iniciar sólo PostgreSQL. Preparar Flyway sin bootstrap, HTTP, TCP ni scheduler:

```bash
docker compose build
docker compose up -d katana-db
docker compose run --rm --no-deps katana-backend --migrate-only
python3 scripts/import-katana.py --backup backups/DIRECTORIO --container katana-local-katana-db-1
python3 scripts/import-katana.py --backup backups/DIRECTORIO --container katana-local-katana-db-1
```

5. Antes de iniciar el backend, configurar ADMIN_EMAIL con el correo exacto de un
   ADMIN importado, ADMIN_PASSWORD con una contraseña nueva fuerte y
   RECOVER_IMPORTED_ADMIN=true. El bootstrap sólo permite recuperar una cuenta
   importada ADMIN marcada reset_required; audita la operación y revoca sesiones.
   Iniciar backend, confirmar login, poner RECOVER_IMPORTED_ADMIN=false y recrear
   el backend. Los demás usuarios se restablecen desde Usuarios/configuración.
   Si el respaldo no contiene ADMIN, no promover silenciosamente un operador:
   un administrador de la laptop debe revisar y autorizar una cuenta de recuperación.
6. Confirmar que el receptor anterior está detenido y los puertos 8300/28080/28082
   están libres. `docker compose up -d --build`. Comprobar los tres healthchecks,
   login y conteos. Mantener nodos físicos desconectados hasta el ensayo acordado.
7. Hacer `python3 scripts/backup-local.py` y ensayar restauración en otra base nueva.

La importación usa BEGIN/COMMIT y aborta completamente si un valor no es válido.
No continuar sobre una base parcialmente preparada manualmente; usar otra base
vacía y conservar el intento para inspección. El ensayo automatizado verifica
rollback con una muestra inválida y rechazo de checksums alterados.

## Rollback

Detener Katana nuevo sin borrar volumen; guardar un dump de sus filas nuevas.
Reiniciar los contenedores anteriores con sus imágenes/configuración y volúmenes
conservados sólo cuando 8300 esté libre. Conciliar los datos posteriores al corte
antes de repetir una migración: el importador no hace fusión incremental.

## Restauración del respaldo local

Verificar SHA256 de katana.dump contra manifest.json; iniciar otro PostgreSQL 17
con un volumen nuevo y una base vacía. Ejecutar:

```bash
docker exec -i CONTENEDOR_NUEVO pg_restore --exit-on-error --no-owner --no-acl -U katana -d katana < backups/DIRECTORIO/katana.dump
```

No usar `--clean` sobre un destino operativo. Comparar conteos y comprobar login
antes de mover puertos. El dump incluye sesiones: revocarlas al restaurar si el
respaldo pudo quedar accesible a personas no autorizadas.
