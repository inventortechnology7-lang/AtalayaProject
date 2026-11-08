# ATALAYA v2 — progreso y evidencia

## Auditoría (2026-11-08)
Base main; origin inventortechnology7-lang/AtalayaProjectLaptop; identidad Git Inventor.
El archivo original permanece intacto. Sin MQTT: TCP 8300, HTTP/SSE y puente USB.
Java 21/Spring JDBC, PostgreSQL/Flyway, Python SQLite WAL/outbox; clientes iniciales JS.

Contrato documentado en Registro/Ordenes de Negra.md #006: st.pue A/B,
st.puerta cerrada|abriendo|abierta|cerrando|trabada; el=[Sensor 1,Sensor 2,Motor]
son indicadores 0 OK/1 FALLA, NO posición ni sensores de obstrucción certificados.
Identidad del nodo = IP; no inventar un identificador de firmware.
Los registros históricos mencionan R4 WiFi, ESP32 y pantalla R4 Minima; también
explican pruebas SIM sin hardware conectado. Corriente/voltaje del simulador
no prueban sensores instalados. Las mediciones se muestran solo cuando llegan.

No hay sketches de producción: protocol_probe es diagnóstico Serial sin actuadores.
ORDEN y REINICIO son líneas TCP literales. No se puede documentar su efecto físico
exacto sin el firmware ausente. No hay evidencia de relé de corte eléctrico.
No se implementa recuperación automática. Ni entrega TCP ni estado posterior
prueban causalidad o ejecución física de un comando.

Brechas iniciales: estado individual no se sincronizaba; comandos dependían solo
del latido Katana; no había centro persistente de notificaciones ni filtros paginados;
web/móvil consultaban cada 10 s y mostraban puertas A/B aunque no existieran.

## Fases
- Auditoría: terminada para contratos y rutas operativas; ver límites físicos arriba.
- Datos/backend, eventos, web, móvil e integración: implementados; resultados de continuación abajo.

## Validación física pendiente
Obtener sketches/versiones, inventario de sensores y protecciones, enclavamientos,
semántica de comandos y validación presencial. Push requiere dispositivo Expo real.
Las pruebas automáticas usan bases aisladas y sockets simulados, nunca puertas reales.

## Continuación V2 (2026-11-08)
Se recuperó la rama existente y todos los cambios locales. No se reinició la auditoría,
no se modificó main ni el proyecto original. Primer commit funcional: 200efc1.

### Implementación terminada
- Spring Boot separado en API de ingesta/comandos, puertas, monitoreo, notificaciones,
  autenticación y retención opcional. Flyway V2–V4 agrega estados/eventos A/B,
  alarmas, lecturas de notificaciones por usuario, auditoría y cola Expo.
- Estado y evento de puerta se guardan junto al outbox SQLite en una transacción.
  UID persistentes, histórico idempotente aun si cambia la clasificación del evento,
  tiempo observado separado del recibido; reportes atrasados no pisan estado ni nodo.
- Comandos exigen ADMIN, validación física documentada, confirmación, motivo, estado
  reciente y enlace activo. Vigencia 30 s, intervalo 60 s. Reclamo antes del socket,
  sin reintento tras entrega incierta; pendientes locales se invalidan al reiniciar.
  ORDEN/REINICIO conservan líneas TCP literales. Entrega no confirma movimiento.
- Web React/TypeScript: dashboard, puertas observadas, alarmas con reconocimiento,
  logs filtrados/paginados, historial, controles, validación física y notificaciones
  persistentes. SSE autenticado y temas claro/oscuro.
- Móvil React Native/Expo migrado a TypeScript: estados, alarmas, actividad, historial,
  notificaciones persistentes, registro Expo Push explícito, SSE con consulta de respaldo,
  caché de solo lectura con fecha y borrado al cerrar sesión. Credencial en SecureStore.
  Sin cola de comandos offline. El build y export ejecutan tsc estricto.
- Push deshabilitado por defecto. Registro de tokens, tickets/receipts, reintento
  acotado de notificaciones e invalidación DeviceNotRegistered. Se distingue aceptación
  del proveedor de recepción real. Retención de contactos opt-in, mínimo 30 días.

### Evidencia comprobada hasta este punto
- TS2882 resuelto por vite-env.d.ts; tsc y build web pasan.
- 27 pruebas edge pasan, incluidas caducidad, caída tras reclamo, incertidumbre,
  atomicidad de estado/outbox y puertas independientes. El fallo previo de TCP fue
  una restricción del sandbox: se verificó con sockets loopback autorizados.
- 7 pruebas Spring Boot con PostgreSQL 17 real pasan, Flyway V1–V4.
  Se corrigieron JSON opcional/cast jsonb e identidad del UID en replays.
- Exportación Hermes Android e iOS completada con TypeScript 6 compatible con Expo.
  expo install --check pasa; npm audit web y móvil: 0 vulnerabilidades.
- Docker Compose construido e iniciado, puertos edge limitados a loopback.
- Integración TCP → SQLite → HTTP → PostgreSQL y SSE → socket Unix → TCP simulados:
  bloqueo sin validación, A/B independientes, notificación persistente, caída backend,
  acceso local offline, reinicio edge y recuperación sin duplicación. Importación
  histórica repetida preserva UIDs y base fuente.
- Playwright: 2 pruebas pasan a 1280 y 390 px tras corregir el desbordamiento.
  CI actualizado para esta rama y PR a main; conserva capturas como artefactos.

### Límites de entrega
La caché móvil conserva una instantánea privada en el almacenamiento de la aplicación;
no es almacenamiento histórico completo ni permite operaciones offline. Web necesita
backend para una sesión nueva; acceso local offline sigue disponible en Katana.
Los logs sin puerta explícita permanecen sin asignar. Reconocer una alarma es un registro
del operador en el servidor; no cambia bits de falla ni confirma reparación del nodo.
No hay firmware de producción ni dispositivos/sensores nuevos. Recuperación eléctrica
automática deshabilitada. Faltan inventario y validación presencial de protecciones,
enclavamientos y semántica física de ORDEN/REINICIO.
Expo Push requiere proyecto EAS, credenciales APNs/FCM, build y dispositivo real;
no se ha enviado ni validado push real. Exportar JS no equivale a generar APK/IPA.
