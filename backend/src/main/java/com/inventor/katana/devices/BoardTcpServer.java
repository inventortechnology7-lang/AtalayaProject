package com.inventor.katana.devices;

import com.fasterxml.jackson.core.StreamReadConstraints;
import com.fasterxml.jackson.databind.DeserializationFeature;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.io.*;
import java.net.*;
import java.nio.ByteBuffer;
import java.nio.charset.*;
import java.security.MessageDigest;
import java.time.*;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.locks.ReentrantLock;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

/** Bounded Java 21 virtual-thread transport. No HTTP client, remote command or actuator API. */
public final class BoardTcpServer implements AutoCloseable {
    public static final int PORT = 8300;
    public static final int MAX_LINE_BYTES = 64 * 1024;
    private static final Logger log = LoggerFactory.getLogger(BoardTcpServer.class);
    private final ServerSocket server;
    private final byte[] token;
    private final BoardSink sink;
    private final Clock clock;
    private final int authenticationMs, idleMs;
    private final Duration syncInterval;
    private final Semaphore slots;
    private final Set<Client> clients = ConcurrentHashMap.newKeySet();
    private final ConcurrentMap<String, Client> nodes = new ConcurrentHashMap<>();
    private final ExecutorService workers = Executors.newVirtualThreadPerTaskExecutor();
    private final AtomicBoolean running = new AtomicBoolean();
    private final ObjectMapper mapper;

    public BoardTcpServer(InetSocketAddress bind, String secret, BoardSink sink) throws IOException {
        this(bind, secret, sink, Clock.systemUTC(), Duration.ofSeconds(10), Duration.ofSeconds(120), Duration.ofSeconds(15), 128);
    }
    BoardTcpServer(InetSocketAddress bind, String secret, BoardSink sink, Clock clock,
                   Duration authTimeout, Duration idleTimeout, Duration syncInterval, int maxConnections) throws IOException {
        if (secret == null || secret.isBlank() || secret.contains("\n") || secret.contains("\r") || secret.length() > 4096)
            throw new IllegalArgumentException("PLACA_TOKEN required; one bounded line");
        if (maxConnections < 1 || authTimeout.isNegative() || authTimeout.isZero() || idleTimeout.isNegative()
                || idleTimeout.isZero() || syncInterval.isNegative() || syncInterval.isZero()) throw new IllegalArgumentException("invalid_limits");
        this.token = secret.strip().getBytes(StandardCharsets.UTF_8);
        this.sink = Objects.requireNonNull(sink); this.clock = clock;
        this.authenticationMs = Math.toIntExact(authTimeout.toMillis()); this.idleMs = Math.toIntExact(idleTimeout.toMillis());
        this.syncInterval = syncInterval; this.slots = new Semaphore(maxConnections);
        mapper = new ObjectMapper().enable(DeserializationFeature.FAIL_ON_TRAILING_TOKENS);
        mapper.getFactory().setStreamReadConstraints(StreamReadConstraints.builder().maxNestingDepth(32).maxStringLength(MAX_LINE_BYTES).build());
        server = new ServerSocket();
        try { server.bind(bind, maxConnections); } catch (IOException e) { server.close(); workers.close(); throw e; }
    }
    private Set<String> screenOrigins = Set.of();
    public void screenOrigins(Set<String> origins) { screenOrigins = Set.copyOf(origins); }
    public void refreshScreens() {
        var lines = sink.screenLines();
        for (var entry : nodes.entrySet()) if (screenOrigins.contains(entry.getKey())) {
            try { for (String line : lines) entry.getValue().send(line); } catch (IOException e) { entry.getValue().close(); }
        }
    }
    public int port() { return server.getLocalPort(); }
    public void start() {
        if (!running.compareAndSet(false, true)) throw new IllegalStateException("already_started");
        workers.submit(() -> {
            while (running.get()) {
                try {
                    Socket socket = server.accept();
                    if (!slots.tryAcquire()) { socket.close(); continue; }
                    Client client = new Client(socket); clients.add(client);
                    workers.submit(() -> serve(client));
                } catch (IOException e) { if (running.get()) log.warn("event=tcp_accept_failed reason={}", e.getClass().getSimpleName()); }
            }
        });
    }
    private void serve(Client client) {
        Future<?> heartbeat = null; boolean authenticated = false;
        String node = client.socket.getInetAddress().getHostAddress();
        try {
            client.socket.setTcpNoDelay(true);
            InputStream input = client.socket.getInputStream();
            String first = readLine(input, client.socket, authenticationMs, 4096);
            if (first == null || !first.startsWith("TOKEN ") || !MessageDigest.isEqual(token, first.substring(6).strip().getBytes(StandardCharsets.UTF_8))) {
                log.warn("event=tcp_auth_rejected node={} connection={}", node, client.id); return;
            }
            // The sink uses the connection UUID to fence old disconnects and writes.
            synchronized (nodes) {
                sink.connected(client.id, node, client.socket.getRemoteSocketAddress().toString(), clock.instant());
                authenticated = true;
                Client previous = nodes.put(node, client);
                if (previous != null) previous.close();
            }
            client.send("HORA " + clock.instant().getEpochSecond());
            if (screenOrigins.contains(node)) for (String line : sink.screenLines()) client.send(line);
            heartbeat = workers.submit(() -> {
                try {
                    while (!client.socket.isClosed()) { Thread.sleep(syncInterval); client.send("SYNC"); }
                } catch (InterruptedException e) { Thread.currentThread().interrupt(); }
                  catch (IOException e) { client.close(); }
            });
            log.info("event=tcp_connected node={} connection={}", node, client.id);
            while (!client.socket.isClosed()) {
                String line = readLine(input, client.socket, idleMs, MAX_LINE_BYTES);
                if (line == null) break;
                BoardMessage message;
                try { message = BoardMessage.parse(mapper, line); }
                catch (IOException | IllegalArgumentException e) {
                    log.warn("event=tcp_invalid_frame node={} connection={}", node, client.id); continue;
                }
                sink.received(client.id, node, message, clock.instant());
            }
        } catch (Exception e) {
            // Never log TOKEN, a raw frame, SQL parameters, or remote-controlled exception text.
            log.info("event=tcp_closed node={} connection={} reason={}", node, client.id, e.getClass().getSimpleName());
        } finally {
            if (heartbeat != null) heartbeat.cancel(true);
            client.close(); clients.remove(client); nodes.remove(node, client);
            if (authenticated) {
                try { sink.disconnected(client.id, node, clock.instant()); }
                catch (RuntimeException e) { log.error("event=tcp_disconnect_persist_failed connection={}", client.id); }
            }
            slots.release();
        }
    }
    /** Deadline covers the complete frame, preventing slow byte-by-byte clients from holding slots. */
    static String readLine(InputStream input, Socket socket, int timeoutMs, int limit) throws IOException {
        long deadline = System.nanoTime() + TimeUnit.MILLISECONDS.toNanos(timeoutMs);
        ByteArrayOutputStream bytes = new ByteArrayOutputStream(Math.min(limit, 1024));
        while (true) {
            long left = deadline - System.nanoTime();
            if (left <= 0) throw new SocketTimeoutException("frame_timeout");
            socket.setSoTimeout((int)Math.max(1, TimeUnit.NANOSECONDS.toMillis(left)));
            int b = input.read();
            if (b < 0) { if (bytes.size() == 0) return null; throw new EOFException("partial_frame"); }
            if (b == '\n') break;
            if (bytes.size() >= limit) throw new IOException("frame_too_large");
            bytes.write(b);
        }
        return StandardCharsets.UTF_8.newDecoder().onMalformedInput(CodingErrorAction.REPORT)
                .decode(ByteBuffer.wrap(bytes.toByteArray())).toString().strip();
    }
    @Override public void close() {
        running.set(false);
        try { server.close(); } catch (IOException ignored) { }
        clients.forEach(Client::close); workers.shutdownNow();
        try { if (!workers.awaitTermination(5, TimeUnit.SECONDS)) log.warn("event=tcp_shutdown_timeout"); }
        catch (InterruptedException e) { Thread.currentThread().interrupt(); }
    }
    private static final class Client {
        final UUID id = UUID.randomUUID(); final Socket socket;
        final ReentrantLock writeLock = new ReentrantLock();
        Client(Socket socket) { this.socket = socket; }
        void send(String line) throws IOException {
            writeLock.lock();
            try { socket.getOutputStream().write((line + "\n").getBytes(StandardCharsets.UTF_8)); socket.getOutputStream().flush(); }
            finally { writeLock.unlock(); }
        }
        void close() { try { socket.close(); } catch (IOException ignored) { } }
    }
}
