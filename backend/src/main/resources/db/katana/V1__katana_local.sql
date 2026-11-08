-- New, isolated database only. Never run against the legacy central volume.
CREATE TABLE roles (name varchar(16) PRIMARY KEY CHECK (name IN ('ADMIN','TECNICO','OPERADOR')));
INSERT INTO roles VALUES ('ADMIN'),('TECNICO'),('OPERADOR');
CREATE TABLE users (
 email varchar(254) PRIMARY KEY, name varchar(200) NOT NULL,
 role varchar(16) NOT NULL REFERENCES roles(name), password_hash varchar(100),
 active boolean NOT NULL DEFAULT true, reset_required boolean NOT NULL DEFAULT false,
 created_at timestamptz NOT NULL DEFAULT now(),
 CHECK (password_hash IS NOT NULL OR reset_required));
CREATE TABLE sessions (
 token_hash char(64) PRIMARY KEY, user_email varchar(254) NOT NULL REFERENCES users(email),
 created_at timestamptz NOT NULL DEFAULT now(), expires_at timestamptz NOT NULL);
CREATE INDEX sessions_expiry ON sessions(expires_at);
CREATE TABLE devices (
 node varchar(200) PRIMARY KEY, address varchar(256), systems jsonb NOT NULL DEFAULT '[]',
 config jsonb, screen_state jsonb, first_seen timestamptz NOT NULL, last_seen timestamptz NOT NULL,
 connected boolean NOT NULL DEFAULT false, current_connection uuid,
 CHECK (jsonb_typeof(systems)='array'));
CREATE TABLE device_connections (
 id uuid PRIMARY KEY, node varchar(200) NOT NULL REFERENCES devices(node),
 address varchar(256) NOT NULL, connected_at timestamptz NOT NULL, disconnected_at timestamptz);
CREATE INDEX connections_node_time ON device_connections(node,connected_at DESC);
CREATE TABLE doors (
 id char(1) PRIMARY KEY CHECK(id IN ('A','B')), node varchar(200) NOT NULL REFERENCES devices(node));
CREATE TABLE door_status (
 door_id char(1) PRIMARY KEY REFERENCES doors(id), reported_state varchar(100),
 sensor_1 smallint CHECK(sensor_1 IN (0,1)), sensor_2 smallint CHECK(sensor_2 IN (0,1)),
 motor smallint CHECK(motor IN (0,1)), uptime bigint CHECK(uptime>=0),
 observed_at timestamptz NOT NULL, last_contact timestamptz NOT NULL, offline boolean NOT NULL DEFAULT false);
CREATE TABLE door_events (
 uid varchar(128) PRIMARY KEY, door_id char(1) NOT NULL REFERENCES doors(id),
 node varchar(200) NOT NULL REFERENCES devices(node), kind varchar(32) NOT NULL,
 severity smallint NOT NULL CHECK(severity BETWEEN 0 AND 3), occurred_at timestamptz NOT NULL, payload jsonb NOT NULL);
CREATE INDEX door_events_time ON door_events(door_id,occurred_at DESC,uid);
CREATE INDEX door_events_severity ON door_events(severity,occurred_at DESC);
CREATE TABLE alarms (
 uid varchar(128) PRIMARY KEY, node varchar(200) NOT NULL REFERENCES devices(node),
 door_id char(1) REFERENCES doors(id), system varchar(200) NOT NULL,
 severity smallint NOT NULL CHECK(severity BETWEEN 0 AND 3), detail text NOT NULL,
 source varchar(16) NOT NULL CHECK(source IN ('BOARD','MONITOR','IMPORT')),
 board_acknowledged boolean NOT NULL DEFAULT false, acknowledged_by varchar(254) REFERENCES users(email),
 acknowledged_at timestamptz, opened_at timestamptz NOT NULL, closed_at timestamptz,
 raw_time numeric, active boolean NOT NULL DEFAULT true);
CREATE INDEX alarms_active_severity ON alarms(active,severity,opened_at DESC);
CREATE INDEX alarms_door_time ON alarms(door_id,opened_at DESC);
CREATE TABLE alarm_history (
 id bigserial PRIMARY KEY, alarm_uid varchar(128) NOT NULL REFERENCES alarms(uid),
 kind varchar(32) NOT NULL, occurred_at timestamptz NOT NULL, actor varchar(254) REFERENCES users(email), payload jsonb NOT NULL);
CREATE INDEX alarm_history_time ON alarm_history(alarm_uid,occurred_at DESC);
CREATE TABLE telemetry_samples (
 uid varchar(128) PRIMARY KEY, node varchar(200) NOT NULL REFERENCES devices(node),
 system varchar(200) NOT NULL, magnitude varchar(200) NOT NULL, value double precision NOT NULL,
 unit varchar(100) NOT NULL, received_at timestamptz NOT NULL,
 CHECK(value NOT IN ('Infinity'::float8,'-Infinity'::float8,'NaN'::float8)));
CREATE INDEX telemetry_time ON telemetry_samples(system,magnitude,received_at DESC,uid);
CREATE TABLE system_logs (
 uid varchar(128) PRIMARY KEY, node varchar(200) REFERENCES devices(node), door_id char(1) REFERENCES doors(id),
 system varchar(200) NOT NULL, severity smallint NOT NULL CHECK(severity BETWEEN 0 AND 3),
 message text NOT NULL, occurred_at timestamptz NOT NULL, received_at timestamptz NOT NULL DEFAULT now(), raw_time numeric);
CREATE INDEX logs_time ON system_logs(occurred_at DESC,uid);
CREATE INDEX logs_door_time ON system_logs(door_id,occurred_at DESC);
CREATE INDEX logs_severity_time ON system_logs(severity,occurred_at DESC);
CREATE TABLE audit_logs (
 id bigserial PRIMARY KEY, actor varchar(254), action varchar(100) NOT NULL, target varchar(256),
 occurred_at timestamptz NOT NULL DEFAULT now(), detail jsonb NOT NULL DEFAULT '{}');
CREATE INDEX audit_time ON audit_logs(occurred_at DESC);
-- Preserve command/outbox evidence without introducing any runnable command queue.
CREATE TABLE legacy_records (
 source_sha256 char(64) NOT NULL, source_table varchar(100) NOT NULL,
 source_key text NOT NULL, payload jsonb NOT NULL,
 PRIMARY KEY(source_sha256,source_table,source_key));
CREATE TABLE import_runs (
 source_sha256 char(64) PRIMARY KEY, imported_at timestamptz NOT NULL DEFAULT now(), counts jsonb NOT NULL);
