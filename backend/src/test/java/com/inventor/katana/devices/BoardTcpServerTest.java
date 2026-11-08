package com.inventor.katana.devices;

import com.fasterxml.jackson.databind.*;
import java.io.*;
import java.net.*;
import java.nio.charset.StandardCharsets;
import java.time.*;
import java.util.*;
import java.util.concurrent.*;
import org.junit.jupiter.api.*;
import static org.junit.jupiter.api.Assertions.*;

class BoardTcpServerTest {
    record Received(UUID connection, String node, BoardMessage message) { }
    final BlockingQueue<Received> received = new LinkedBlockingQueue<>();
    final BlockingQueue<UUID> connected = new LinkedBlockingQueue<>(), disconnected = new LinkedBlockingQueue<>();
    BoardTcpServer server;
    @BeforeEach void start() throws Exception {
        server = new BoardTcpServer(new InetSocketAddress("127.0.0.1",0), "test-secret", new BoardSink() {
            public void connected(UUID id,String node,String address,Instant at) { connected.add(id); }
            public void received(UUID id,String node,BoardMessage message,Instant at) { received.add(new Received(id,node,message)); }
            public void disconnected(UUID id,String node,Instant at) { disconnected.add(id); }
        }, Clock.fixed(Instant.ofEpochSecond(1794090000),ZoneOffset.UTC), Duration.ofMillis(300), Duration.ofMillis(800), Duration.ofMillis(100), 4);
        server.start();
    }
    @AfterEach void stop() { server.close(); }
    Socket socket() throws Exception { Socket s=new Socket("127.0.0.1",server.port()); s.setSoTimeout(2000); return s; }
    static void send(Socket s,String value) throws Exception { s.getOutputStream().write(value.getBytes(StandardCharsets.UTF_8)); s.getOutputStream().flush(); }
    static BufferedReader reader(Socket s) throws Exception { return new BufferedReader(new InputStreamReader(s.getInputStream(),StandardCharsets.UTF_8)); }
    @Test void tokenHoraSyncAndAllFrames() throws Exception {
        try(Socket s=socket()) {
            send(s,"TOKEN test-secret\r\n"); var r=reader(s);
            assertEquals("HORA 1794090000",r.readLine());
            send(s,"{\"cfg\":{\"cor\":[\"Puertas\"]},\"st\":{\"pue\":\"A\",\"puerta\":\"cerrada\",\"el\":[0,0,1],\"up\":5,\"al\":[[0,2,0,1794090000,\"motor\"]]},\"logs\":[[1794090000,0,\"Puertas\",\"inicio\"]],\"log\":{\"t\":1794090001,\"v\":1,\"s\":\"Puertas\",\"m\":\"aviso\"},\"m\":[[\"Puertas\",\"voltaje\",12.3,\"V\"]]}\n");
            var frame=received.poll(2,TimeUnit.SECONDS); assertNotNull(frame); assertEquals("127.0.0.1",frame.node());
            assertEquals(1,frame.message().body().path("st").path("el").get(2).asInt());
            assertEquals("SYNC",r.readLine());
        }
        assertNotNull(disconnected.poll(2,TimeUnit.SECONDS));
    }
    @Test void invalidTokenCannotRegisterOrWrite() throws Exception {
        try(Socket s=socket()) { send(s,"TOKEN wrong\n"); assertEquals(-1,s.getInputStream().read()); }
        assertTrue(connected.isEmpty()); assertTrue(received.isEmpty());
    }
    @Test void authenticationHasDeadline() throws Exception {
        try(Socket s=socket()) { send(s,"TOK"); assertEquals(-1,s.getInputStream().read()); }
        assertTrue(connected.isEmpty());
    }
    @Test void malformedFrameDoesNotPartiallyReachSink() throws Exception {
        try(Socket s=socket()) {
            send(s,"TOKEN test-secret\n"); reader(s).readLine();
            send(s,"{\"cfg\":{\"cor\":[\"Puertas\"]},\"m\":[[\"Puertas\",\"voltaje\",\"bad\",\"V\"]]}\n");
            send(s,"{\"st\":{\"pue\":\"B\",\"el\":[0,1,0]}}\n");
            var frame=received.poll(2,TimeUnit.SECONDS); assertNotNull(frame); assertEquals("B",frame.message().body().path("st").path("pue").asText());
            assertTrue(received.isEmpty());
        }
    }
    @Test void oversizedLineClosesConnection() throws Exception {
        try(Socket s=socket()) {
            send(s,"TOKEN test-secret\n"); var r=reader(s); r.readLine();
            try { send(s,"x".repeat(BoardTcpServer.MAX_LINE_BYTES+1)+"\n"); } catch(SocketException expected) { }
            assertNotNull(disconnected.poll(2,TimeUnit.SECONDS)); assertTrue(received.isEmpty());
        }
    }
    @Test void reconnectReplacesSameIpAndUsesNewConnectionIdentity() throws Exception {
        try(Socket a=socket();Socket b=socket()) {
            send(a,"TOKEN test-secret\n"); reader(a).readLine(); UUID first=connected.poll(2,TimeUnit.SECONDS);
            send(b,"TOKEN test-secret\n"); reader(b).readLine(); UUID second=connected.poll(2,TimeUnit.SECONDS);
            assertNotEquals(first,second); assertEquals(first,disconnected.poll(2,TimeUnit.SECONDS));
            send(b,"{\"cfg\":{\"cor\":[]}}\n"); assertEquals(second,received.poll(2,TimeUnit.SECONDS).connection());
        }
    }
    @Test void rejectsTrailingObjectsAndInvalidTypes() {
        ObjectMapper mapper=new ObjectMapper().enable(DeserializationFeature.FAIL_ON_TRAILING_TOKENS);
        for(String line:List.of("[]","{\"st\":{}}{}","{\"st\":{\"pue\":\"C\"}}","{\"st\":{\"el\":[0,0,2]}}","{\"log\":{\"v\":9}}","{\"cfg\":{\"cor\":{}}}"))
            assertThrows(Exception.class,()->BoardMessage.parse(mapper,line));
    }
}
