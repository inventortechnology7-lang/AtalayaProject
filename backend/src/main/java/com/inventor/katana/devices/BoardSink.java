package com.inventor.katana.devices;

import java.time.Instant;
import java.util.UUID;

/** Each callback must commit atomically before returning. Never enqueue physical commands. */
public interface BoardSink {
    void connected(UUID connection, String node, String address, Instant at);
    void received(UUID connection, String node, BoardMessage message, Instant at);
    void disconnected(UUID connection, String node, Instant at);
}
