#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
name="katana-test-$$"
cleanup() { docker rm -f "$name-db" >/dev/null 2>&1 || true; docker network rm "$name" >/dev/null 2>&1 || true; }
trap cleanup EXIT
docker network create "$name" >/dev/null
docker run -d --name "$name-db" --network "$name" --network-alias postgres --tmpfs /var/lib/postgresql/data -e POSTGRES_DB=katana -e POSTGRES_USER=katana -e POSTGRES_PASSWORD=test-only-password postgres:17-alpine >/dev/null
for i in {1..60}; do if docker exec "$name-db" pg_isready -h 127.0.0.1 -U katana -d katana >/dev/null 2>&1; then break; fi; sleep 1; done
docker run --rm --network "$name" -v "$PWD/backend:/src" -v katana-maven-cache:/root/.m2 -w /src \
 -e DB_URL=jdbc:postgresql://postgres:5432/katana -e DB_PASSWORD=test-only-password \
 -e ADMIN_EMAIL=admin@test.local -e ADMIN_PASSWORD=admin-test-password-123 \
 -e PLACA_TOKEN=test-board-secret -e TCP_PORT=0 \
 maven:3.9.9-eclipse-temurin-21 mvn -B clean -Dtest=BoardTcpServerTest,LocalIntegrationTest verify
