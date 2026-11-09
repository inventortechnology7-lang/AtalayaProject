ALTER TABLE sessions ADD COLUMN id uuid NOT NULL DEFAULT gen_random_uuid() UNIQUE;
CREATE TABLE login_attempts(id bigserial PRIMARY KEY, account_key char(64) NOT NULL, address_key char(64) NOT NULL, occurred_at timestamptz NOT NULL DEFAULT now());
CREATE INDEX login_attempts_time ON login_attempts(occurred_at);
CREATE TABLE monitoring_settings(id smallint PRIMARY KEY CHECK(id=1), silence_seconds integer NOT NULL CHECK(silence_seconds BETWEEN 30 AND 3600));
INSERT INTO monitoring_settings VALUES(1,120);
