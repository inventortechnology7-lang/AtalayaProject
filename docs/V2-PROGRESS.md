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
- Datos/backend, eventos, web, móvil e integración: en implementación.

## Validación física pendiente
Obtener sketches/versiones, inventario de sensores y protecciones, enclavamientos,
semántica de comandos y validación presencial. Push requiere dispositivo Expo real.
Las pruebas automáticas usan bases aisladas y sockets simulados, nunca puertas reales.
