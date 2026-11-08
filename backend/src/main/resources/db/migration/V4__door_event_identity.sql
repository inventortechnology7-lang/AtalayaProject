-- A replay keeps its UID even when its classification would change.
CREATE UNIQUE INDEX door_event_identity ON door_events(condo,uid) WHERE kind IN ('estado','contacto');
