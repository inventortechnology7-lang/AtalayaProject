-- Additive migration. Legacy tables and UIDs remain authoritative and untouched.
CREATE VIEW users AS SELECT email,role,condo FROM account;
CREATE VIEW commands AS SELECT * FROM command;
CREATE TABLE doors (
 condo bigint NOT NULL, id text NOT NULL CHECK(id IN ('A','B')), node text NOT NULL,
 safety_validated boolean NOT NULL DEFAULT false, safety_evidence text,
 PRIMARY KEY(condo,id));
CREATE TABLE door_status (
 condo bigint NOT NULL, door_id text NOT NULL, state text NOT NULL,
 raw jsonb NOT NULL, observed timestamptz NOT NULL,
 PRIMARY KEY(condo,door_id), FOREIGN KEY(condo,door_id) REFERENCES doors(condo,id));
CREATE TABLE door_events (
 id bigserial PRIMARY KEY, condo bigint NOT NULL, uid text NOT NULL, kind text NOT NULL,
 door_id text, severity int NOT NULL DEFAULT 0 CHECK(severity BETWEEN 0 AND 3),
 occurred timestamptz NOT NULL, received timestamptz NOT NULL DEFAULT now(), payload jsonb NOT NULL,
 UNIQUE(condo,kind,uid), FOREIGN KEY(condo,door_id) REFERENCES doors(condo,id));
CREATE INDEX door_events_time ON door_events(condo,occurred DESC,id DESC);
CREATE INDEX door_events_door_time ON door_events(condo,door_id,occurred DESC);
CREATE INDEX door_events_severity ON door_events(condo,severity,occurred DESC);
CREATE TABLE alarms (
 condo bigint NOT NULL, uid text NOT NULL, payload jsonb NOT NULL,
 acknowledged_by text REFERENCES account(email), acknowledged_at timestamptz,
 PRIMARY KEY(condo,uid));
CREATE TABLE notifications (
 id bigserial PRIMARY KEY, condo bigint NOT NULL, source text NOT NULL, payload jsonb NOT NULL,
 created timestamptz NOT NULL DEFAULT now(), UNIQUE(condo,source));
CREATE INDEX notification_recent ON notifications(condo,created DESC);
CREATE TABLE notification_reads (
 notification_id bigint REFERENCES notifications(id) ON DELETE CASCADE,
 email text REFERENCES account(email), read_at timestamptz NOT NULL DEFAULT now(), PRIMARY KEY(notification_id,email));
CREATE TABLE audit_logs (
 id bigserial PRIMARY KEY, condo bigint NOT NULL, actor text NOT NULL REFERENCES account(email),
 action text NOT NULL, target text NOT NULL, detail jsonb NOT NULL, created timestamptz NOT NULL DEFAULT now());
CREATE INDEX audit_recent ON audit_logs(condo,created DESC);
ALTER TABLE command ADD COLUMN confirmation text;
ALTER TABLE command ADD COLUMN delivery_result text;
ALTER TABLE command ADD COLUMN reported timestamptz;
-- Project existing telemetry without modifying it; alarm revisions retain their own immutable snapshot.
CREATE FUNCTION project_telemetry() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 INSERT INTO door_events(condo,uid,kind,severity,occurred,payload)
 VALUES(NEW.condo,NEW.uid || CASE WHEN NEW.kind='alarmas' THEN ':'||md5(NEW.payload::text) ELSE '' END,
 NEW.kind,coalesce((NEW.payload->>'severidad')::int,0),
 coalesce(NEW.payload->>'t',NEW.payload->>'tomada',NEW.payload->>'creada')::timestamptz,NEW.payload)
 ON CONFLICT DO NOTHING;
 IF NEW.kind='alarmas' THEN
 INSERT INTO alarms(condo,uid,payload) VALUES(NEW.condo,NEW.uid,NEW.payload)
 ON CONFLICT(condo,uid) DO UPDATE SET payload=excluded.payload;
 INSERT INTO notifications(condo,source,payload)
 VALUES(NEW.condo,NEW.uid||':'||(NEW.payload->>'estado'),NEW.payload) ON CONFLICT DO NOTHING;
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER telemetry_projection AFTER INSERT OR UPDATE ON telemetry FOR EACH ROW EXECUTE FUNCTION project_telemetry();
-- Backfill invokes the same idempotent projection; legacy received timestamps are preserved.
UPDATE telemetry SET payload=payload;
