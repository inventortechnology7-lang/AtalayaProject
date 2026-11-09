# Katana Local

Supervisión local de puertas A/B y nodos Arduino/ESP32. Spring Boot + PostgreSQL +
React, con cliente React Native. Sin servidor central ni sincronización remota.
No ofrece comandos de movimiento.

## Inicio

Requisitos de preparación: Docker Compose, acceso a imágenes/dependencias al construir.
Después del build no se necesita internet WAN.

```bash
python3 scripts/init-env.py   # sólo si no existe .env; credenciales aleatorias, modo 0600
# Revisar .env: credenciales locales, PLACA_TOKEN y direcciones LAN.
docker compose up -d --build
```

Exactamente tres servicios: `katana-db`, `katana-backend` y `katana-web`.
Web: http://127.0.0.1:28082. API: http://127.0.0.1:28080/api/local.
TCP: 8300. Puertos y direcciones configurables en [.env.example](.env.example).
Los valores por defecto sólo escuchan en localhost. Para teléfonos y placas,
asignar API_BIND/WEB_BIND/TCP_BIND a la IP LAN de esta laptop y limitar el firewall
a la red de confianza. TCP identifica cada nodo por IP: mantener direcciones estables.
El token de placas debe coincidir con el provisionado; nunca se escribe en logs.

El volumen `katana-local_katana-data` es nuevo e independiente de los volúmenes
anteriores. No ejecutar `down -v`, `prune` ni reutilizar el volumen central.
Antes de activar 8300, detener el receptor sustituido; nunca mantener dos receptores
operativos en ese puerto. No hace falta borrar los contenedores ni volúmenes antiguos.

Roles: OPERADOR consulta, TECNICO reconoce alarmas y ADMIN administra usuarios y
parámetros. Sesiones de 12 horas, hashes BCrypt y revocación al cambiar un usuario.
API documentada en `/api/local/openapi` con autenticación. SSE en `/api/local/events`.
Las pantallas distinguen sensores observados de datos indisponibles por desconexión.

## Migración y recuperación

Ver [procedimiento de migración](docs/katana/MIGRATION.md) antes de iniciar una base
que vaya a recibir información histórica. `scripts/backup-katana.py` conserva el
respaldo original SQLite y PostgreSQL; `scripts/import-katana.py` importa a una
base nueva, sin ejecutar órdenes históricas. Usuarios importados requieren reset.

Respaldo PostgreSQL actual:

```bash
python3 scripts/backup-local.py
```

Los respaldos quedan en `backups/`, permisos privados y sin versionar.
Copiarlos a almacenamiento protegido externo. Para restaurar, crear otro volumen,
verificar SHA256 y usar `pg_restore --exit-on-error --no-owner --no-acl` en una base
vacía. Probar la restauración antes de cambiar los puertos. Conservar los datos
recibidos después del respaldo: un rollback no recupera automáticamente esas filas.

## Cliente móvil y USB

Ver [mobile/README.md](mobile/README.md). El cliente usa sólo APIs locales,
SecureStore, SSE con reconexión y caché de lectura marcada con fecha.
La pantalla USB utiliza [usb/puente_pantalla.py](usb/puente_pantalla.py), el único
adaptador Python operativo permitido; no sustituye ni inicia un receptor.

```bash
python3 -m pip install -r usb/requirements.txt
python3 usb/puente_pantalla.py --servidor 127.0.0.1 --token-archivo .env
```

Configurar PANTALLA_ORIGEN con la IP origen que ve el backend Docker, normalmente
el gateway del puente para un adaptador ejecutado en el host. EL 30–35 representa
Sensor 1/Sensor 2/Motor de A y B. La prueba de software no certifica la pantalla física.

## Validación reproducible

```bash
bash scripts/test-backend.sh
python3 scripts/test-katana-migration.py
python3 -m unittest discover -s usb -v
npm ci --prefix web
npx --prefix web playwright install --with-deps chromium
python3 scripts/verify-stack.py
npm ci --prefix mobile
npm run export --prefix mobile
```

`verify-stack.py` requiere Docker Linux y usa `katana-verify`, su propio volumen,
una red sin WAN y simuladores. Incluye Playwright 1440/390 px; capturas en
`web/test-results`. No ejecutarlo contra producción ni simultáneamente con otro
simulador. `CHROMIUM_PATH` permite usar un Chromium ya instalado.
Consultar [implementación y límites](docs/katana/IMPLEMENTATION.md).
