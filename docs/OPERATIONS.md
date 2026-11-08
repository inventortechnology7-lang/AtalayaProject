# Operación y seguridad

## Despliegue
La composición predeterminada es un laboratorio local. Para producción publicar la
web/API detrás de un proxy HTTPS y permitir TCP 8300 solo desde la LAN de placas.
Configurar EDGE_BIND con la IP LAN de Katana, no abrirla a Internet. Usar firewall y
Tailscale/VPN para Katana–Negra. TCP conserva el token en texto del contrato original;
requiere red de confianza. No sustituirlo silenciosamente por un protocolo distinto.

En Katana independiente ejecutar edge/run.py con Python 3.12+, DB_RUTA,
ORDENES_SOCK, ORDENES_DIR, AUTH_DB en directorio persistente y LOCAL_UI_EMAIL /
LOCAL_UI_PASSWORD independientes de las cuentas del backend. Configurar NEGRA_URL,
SYNC_USUARIO, SYNC_CLAVE y CONDOMINIO_ID con el servidor Negra elegido. SQLite
permite seguir recibiendo, registrando y consultando localmente sin WAN. No iniciar
dos receptores sobre el mismo puerto/volumen. El gestor local mantiene login scrypt
independiente y solo lectura; no permite maniobras físicas offline desde la web.

Para pantalla USB instalar pyserial 3.5 en un entorno virtual del host y ejecutar:
`python edge/puente_pantalla.py --servidor 127.0.0.1 --token-archivo /ruta/atalaya.env`.
Si el receptor está en Docker, Docker puede traducir la IP de origen al gateway:
configurar PANTALLA_ORIGEN solo con la IP comprobada del puente; no añadir toda la LAN.
La configuración de producción de USB y firewall se valida en el banco.

## Identidad y autorización
Backend: cuentas BCrypt, tokens aleatorios de 256 bits guardados como SHA-256 en
PostgreSQL, duración 12 h y revocación por /api/logout. Son tokens opacos aceptados
por el cliente original, que no decodifica JWT. Roles ADMIN, VIEWER y EDGE;
condominio ligado a la cuenta, nunca aceptado solo por el cuerpo del request.
ADMIN consulta y crea órdenes; VIEWER consulta; EDGE sincroniza y consume órdenes.
No hay registro público. El bootstrap crea ADMIN y EDGE solo si no existen.
Para incorporar otros condominios/usuarios se requiere aprovisionamiento administrativo
controlado de account (hash BCrypt, rol y condominio); no se ofrece UI multiusuario.

La web conserva el token solo en memoria. React Native usa SecureStore. Las órdenes
requieren confirmación, enlace reciente y vencen en 30 s. El endpoint original de
consumo no aporta ACK físico: una respuesta HTTP perdida puede perder una orden.
No se reintentan maniobras inciertas. Un estado «retirada» significa consumo por
Katana, nunca movimiento confirmado. SSE renueva conexión al cabo de una hora;
los heartbeats detectan órdenes pendientes entre instancias sin polling del cliente.

Login limitado a 20 intentos/minuto/IP por proceso. Un proxy debe añadir límites
compartidos de tráfico si se despliegan réplicas. POST JSON máximo 1 MiB, cadenas
64 KiB, profundidad 20; lote máximo 500 elementos. Consultas limitadas a los últimos
100 registros. Configurar retención según operación: no se borra telemetría automáticamente.

## Secretos existentes
Se encontró un PLACA_TOKEN no vacío en el archivo original Pantalla USB/token.env.
El valor fue retirado del árbol actual, pero sigue en commits históricos. Rotarlo
coordinadamente en Katana, ESP32/R4 y puente USB antes de desplegar; no se modificó
hardware ni se reescribió el historial remoto. Las credenciales del laboratorio son nuevas.

## Backup, restauración y reversión
- PostgreSQL: `docker compose exec -T postgres pg_dump -U atalaya -Fc atalaya > backup.dump`.
  Restaurar en una base vacía con pg_restore; comprobar /health y pruebas de lectura.
- SQLite: usar la API `sqlite3.Connection.backup` para copiar katana.db y usuarios.db
  con WAL activo; no copiar solamente el archivo .db mientras está abierto.
- Respaldar las credenciales por un canal separado, cifrado. Proteger backups porque
  incluyen datos operativos y hashes. Ensayar restauración antes de cambiar producción.
- Reversión: detener el edge nuevo, restaurar el backup previo y arrancar los servicios
  originales. No ejecutar ambos a la vez. Mantener el outbox y sus UID al trasladarlo.
- El cambio a PostgreSQL no copia automáticamente archivos históricos de SQLite:
  el cliente sync drena el outbox pendiente. Para registros ya enviados usar el
  importador descrito abajo; no borrar indicadores enviado en la base operativa.

## Observabilidad
Logs por stdout de contenedores, readiness /health con DB y bootstrap; gestor local
muestra pendientes y último envío. Supervisar crecimiento de SQLite, espacio libre,
registros rechazados (enviado=-1), órdenes inciertas y edad del último latido. El
supervisor edge reinicia todos los workers si uno termina. El volumen conserva datos.

## Importación de históricos SQLite
`scripts/import-sqlite.py backup.db --url http://127.0.0.1:28080 --condominio 1`
inspecciona el backup en modo solo lectura y muestra conteos. Añadir `--apply
--env-file .env` importa alarmas (estado actual), logs y muestras en lotes de 500,
con los UID originales. No modifica el outbox ni copia usuarios/sesiones locales.
Un fallo aborta sin confirmar localmente; se puede repetir por idempotencia.
Realizar la importación antes de conectar el edge al nuevo servidor para evitar que
una alarma histórica sobrescriba un estado más reciente. Un 400 requiere corregir
el dato de origen en una copia revisada; el importador no lo descarta silenciosamente.
