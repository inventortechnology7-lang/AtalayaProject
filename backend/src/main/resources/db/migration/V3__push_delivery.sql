CREATE TABLE push_tokens(token text PRIMARY KEY,email text NOT NULL REFERENCES account(email),registered timestamptz NOT NULL DEFAULT now(),active boolean NOT NULL DEFAULT true);
CREATE TABLE push_deliveries(notification_id bigint REFERENCES notifications(id) ON DELETE CASCADE,token text REFERENCES push_tokens(token),attempts int NOT NULL DEFAULT 0,next_attempt timestamptz NOT NULL DEFAULT now(),ticket text,status text NOT NULL DEFAULT 'pending',error text,PRIMARY KEY(notification_id,token));
CREATE INDEX push_pending ON push_deliveries(next_attempt) WHERE status IN ('pending','ticket');
