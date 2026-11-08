# Migración de AtalayaProjectLaptop

Repositorio exclusivo: inventortechnology7-lang/AtalayaProjectLaptop.
Rama de trabajo: feat/architecture-migration; integración mediante PR a main, sin merge.

## Punto de partida
El commit 4262a4b contiene la aplicación Python original. No contiene un plan previo
ni el texto completo del prompt de migración. Los registros históricos de hardware
se conservan; no se presentan como pruebas de esta migración. Suite inicial: 11/11.

## Decisión de arquitectura
Migración incremental: Katana mantiene SQLite/WAL, TCP y puente USB para operar
sin PostgreSQL, red WAN ni backend. Spring Boot + PostgreSQL implementan el contrato
HTTP de Negra y APIs de consulta autenticadas para React y React Native.
El código original queda archivado; se vació el token versionado de token.env. El runtime edge se copia a edge/.
No se sustituye el firmware instalado ni se energizan actuadores durante pruebas.

## Fases y aceptación
1. Contratos y baseline: fijar protocolo y pruebas existentes.
2. Backend: autenticación, aislamiento de condominio, Flyway, lotes atómicos e
   idempotentes, pantalla, latido, comandos/SSE y consultas; PostgreSQL real.
3. Edge: runtime aislado, persistencia offline, pruebas TCP y recuperación HTTP.
4. Clientes: React web y React Native, sesión, consulta, errores y órdenes explícitas.
5. Operación: Docker, CI, documentación, pruebas de extremo a extremo y PR.

## Límites que requieren banco físico
ESP32, UNO R4 WiFi, Minima/USB, WiFiS3, relés, sensores, reinicio eléctrico y firewall
se verifican en hardware separado. Una compilación o simulación no prueba esos casos.
Los contratos HTTP se deducen del cliente original: el servidor Negra externo y su
documento SINCRONIZACION.md no están incluidos. No se afirma paridad con endpoints
externos no presentes en este repositorio.

## Estado implementado
Fases 1–5 implementadas en commits incrementales: backend compatible, edge offline,
gestor local autenticado, clientes web/móvil, contenedores, sonda de firmware,
importador histórico en solo lectura y CI. Ver VALIDATION.md para resultados.
No se presenta como validación de producción: quedan banco físico, APK/IPA,
Negra remoto, rotación del token histórico y criterios adicionales del prompt original
(no disponible en este checkout). El PR se abre en borrador para revisión, sin merge.

Referencias de implementación: documentación oficial de Spring Boot
https://docs.spring.io/spring-boot/3.5/system-requirements.html y Expo
https://docs.expo.dev/versions/latest/; la compatibilidad final móvil se comprobó
con `expo install --check` sobre las versiones del lockfile.
