# AtalayaProjectLaptop

Migración incremental de Katana y Negra: Spring Boot / PostgreSQL, React web,
React Native, edge Python con SQLite offline y protocolo TCP ESP32 / Arduino.

## Arranque local

Requiere Docker Compose, Python 3 y Node 24 para desarrollar clientes.

```sh
python3 scripts/init-env.py
npm ci --prefix web
npm ci --prefix mobile
docker compose up -d --build
```

- Web React: http://127.0.0.1:28081 — ADMIN_EMAIL / ADMIN_PASSWORD de `.env`.
- API: http://127.0.0.1:28080; readiness: `/health`.
- Gestor Katana offline: http://127.0.0.1:28082 — LOCAL_UI_EMAIL / LOCAL_UI_PASSWORD.
- TCP: 127.0.0.1:8300, PLACA_TOKEN de `.env`.

Las claves se generan al azar, no se imprimen y `.env` tiene permisos 0600.
PostgreSQL no publica puerto. Los datos sobreviven a `docker compose down`;
`down -v` elimina los volúmenes y **no** es un procedimiento de actualización.
Las cuentas se crean solo al primer arranque: cambiar `.env` no rota claves existentes.

## Desarrollo y validación

```sh
python3 -m unittest discover -s edge -v
scripts/test-backend.sh
npm run build --prefix web
npm run export --prefix mobile
python3 scripts/smoke-stack.py
cd web && npx playwright install chromium && npm test
```

La prueba `smoke-stack.py` requiere la pila iniciada y detiene temporalmente **su**
backend y reinicia **su** edge. Genera registros de diagnóstico y una ORDEN hacia
un cliente TCP simulado; usar únicamente en esta instalación de pruebas, sin placas
operativas conectadas. El test web usa esos registros para validar la consulta real.

Móvil: definir `EXPO_PUBLIC_API_URL=https://<servidor>` y ejecutar `npm start` dentro
de mobile. El móvil requiere HTTPS accesible desde el dispositivo. El token se guarda
en SecureStore. La exportación genera bundles; no equivale a instalar APK/IPA.

## Documentación

- [Fases y decisiones](docs/MIGRATION.md)
- [Contratos Katana / Negra](docs/CONTRACTS.md)
- [Operación, backup y seguridad](docs/OPERATIONS.md)
- [Evidencia de validación](docs/VALIDATION.md)
- [ESP32 / Arduino y banco físico](firmware/README.md)

El original se conserva en `pro-20261108T053634Z-1-001/pro/`. Se eliminó únicamente
el valor del token versionado; los contratos originales no requieren cambios en placas.
