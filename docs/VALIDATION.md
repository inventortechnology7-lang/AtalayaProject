# Validación de la migración

Ejecución local 2026-11-08, en AtalayaProjectLaptop / feat/architecture-migration.

| Área | Evidencia |
|---|---|
| Original | 11 pruebas unittest conservadas, todas pasan |
| Edge | 22 unittest: pantalla/puertas/USB, rollback de outbox, reinicio, rechazo 400, TCP real |
| Backend | 4 pruebas Spring Boot con PostgreSQL 17 real, Flyway y HTTP real |
| Integración | TCP → SQLite → API → PostgreSQL; SSE → socket Unix → TCP; corte backend y reinicio edge con recuperación sin duplicar |
| Web | Build Vite; 2 pruebas Chromium a 1280 y 390 px con login, datos reales, cancelación de orden y logout |
| Firmware | Compilación real de sonda para UNO R4 WiFi (60 408 bytes) y ESP32 (890 728 bytes); no flasheo |
| Móvil | Expo con React Native compatible, exportaciones Hermes Android/iOS; no APK/IPA ni ejecución física |
| Dependencias JS | npm audit sin vulnerabilidades tras actualizar Expo y overrides glob/minimatch; versiones fijadas en lockfiles |

Las salidas de ejecución se guardaron en /tmp/atalaya-*.log (no se versionan por
ser artefactos locales). CI reproduce las suites sobre PR. La comprobación de
hardware y los límites de producción están en OPERATIONS.md y firmware/README.md.

No se prueba aquí el servidor Negra remoto, dispositivos ESP32/R4/Minima conectados,
actuadores, WiFi real, firewall de Katana ni restauración de backups de producción.
La prueba de pérdida de backend no simula corrupción de disco o apagado eléctrico.
