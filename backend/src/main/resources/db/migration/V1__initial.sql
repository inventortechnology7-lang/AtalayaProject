CREATE TABLE account (
 email text PRIMARY KEY, password_hash text NOT NULL, role text NOT NULL CHECK(role IN ('ADMIN','VIEWER','EDGE')), condo bigint NOT NULL CHECK(condo>0));
CREATE TABLE session_token (hash text PRIMARY KEY, email text NOT NULL REFERENCES account(email), expires timestamptz NOT NULL);
CREATE INDEX session_expiry ON session_token(expires);
CREATE TABLE telemetry (condo bigint NOT NULL, kind text NOT NULL CHECK(kind IN ('alarmas','logs','muestras')), uid varchar(128) NOT NULL, payload jsonb NOT NULL, received timestamptz NOT NULL DEFAULT now(), PRIMARY KEY(condo,kind,uid));
CREATE INDEX telemetry_recent ON telemetry(condo,kind,received DESC);
CREATE TABLE edge_state (condo bigint PRIMARY KEY, last_seen timestamptz NOT NULL DEFAULT now(), cfg jsonb, st jsonb);
CREATE TABLE command (id bigserial PRIMARY KEY, condo bigint NOT NULL, destino text NOT NULL, accion text NOT NULL, linea text NOT NULL CHECK(linea IN ('ORDEN','REINICIO')), origen text NOT NULL CHECK(origen IN ('app','web')), actor text NOT NULL, created timestamptz NOT NULL DEFAULT now(), expires timestamptz NOT NULL DEFAULT now()+interval '30 seconds', consumed timestamptz);
CREATE INDEX command_pending ON command(condo,id) WHERE consumed IS NULL;
