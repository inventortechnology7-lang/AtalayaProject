package com.inventor.atalaya;
import java.util.*;
import org.junit.jupiter.api.*;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.client.TestRestTemplate;
import org.springframework.http.*;
import org.springframework.jdbc.core.JdbcTemplate;
import static org.assertj.core.api.Assertions.assertThat;

@SpringBootTest(webEnvironment=SpringBootTest.WebEnvironment.RANDOM_PORT)
class ContractTest {
 @Autowired TestRestTemplate http;
 @Autowired JdbcTemplate db;
 String edge,admin;
 @BeforeEach void setup(){db.update("DELETE FROM notification_reads");db.update("DELETE FROM notifications");db.update("DELETE FROM alarms");db.update("DELETE FROM door_events");db.update("DELETE FROM door_status");db.update("DELETE FROM doors");db.update("DELETE FROM audit_logs");db.update("DELETE FROM telemetry");db.update("DELETE FROM command");db.update("DELETE FROM edge_state");edge=login("edge@test.local","edge-test-password-123");admin=login("admin@test.local","admin-test-password-123");}
 String login(String email,String password){return (String)http.postForObject("/api/login",Map.of("correo",email,"clave",password),Map.class).get("token");}
 ResponseEntity<Map> post(String path,String token,String body){HttpHeaders h=new HttpHeaders();h.setContentType(MediaType.APPLICATION_JSON);h.setBearerAuth(token);return http.exchange(path,HttpMethod.POST,new HttpEntity<>(body,h),Map.class);}
 String batch(String logs){return "{\"condominioId\":1,\"alarmas\":[],\"muestras\":[],\"logs\":"+logs+"}";}
 String log="{\"uid\":\"l-test\",\"sistema\":\"Puertas\",\"severidad\":0,\"mensaje\":\"arranque\",\"t\":\"2026-11-08T00:00:00Z\"}";
 @Test void batchIsAtomicAndIdempotent(){
  assertThat(post("/api/sync/lote",edge,batch("["+log+"]")).getBody()).containsEntry("nuevos",1);
  assertThat(post("/api/sync/lote",edge,batch("["+log+"]")).getBody()).containsEntry("duplicados",1);
  assertThat(post("/api/sync/lote",edge,batch("["+log.replace("l-test","l-other")+",{}]")).getStatusCode().value()).isEqualTo(400);
  assertThat(db.queryForObject("SELECT count(*) FROM telemetry",Integer.class)).isEqualTo(1);
 }
 @Test void rejectsUnauthorizedAndOtherTenant(){
  assertThat(http.getForEntity("/api/dashboard",String.class).getStatusCode().value()).isEqualTo(401);
  assertThat(post("/api/sync/latido",edge,"{\"condominioId\":2}").getStatusCode().value()).isEqualTo(403);
  assertThat(post("/api/sync/lote",admin,batch("[]")).getStatusCode().value()).isEqualTo(403);
  assertThat(post("/api/logout",edge,"{}").getStatusCode().value()).isEqualTo(200);
  assertThat(post("/api/sync/latido",edge,"{\"condominioId\":1}").getStatusCode().value()).isEqualTo(401);
 }
 @Test void commandsRequireLiveEdgeAndExpire(){
  String cmd="{\"destino\":\"puerta-A\",\"linea\":\"ORDEN\",\"origen\":\"web\",\"confirmed\":true,\"reason\":\"Banco simulado autorizado\"}";
  assertThat(post("/api/comandos",admin,cmd).getStatusCode().value()).isEqualTo(409);
  post("/api/sync/latido",edge,"{\"condominioId\":1}");
  assertThat(post("/api/comandos",edge,cmd).getStatusCode().value()).isEqualTo(403);
  assertThat(post("/api/comandos",admin,cmd).getStatusCode().value()).isEqualTo(409);
  seedDoor();
  assertThat(post("/api/comandos",admin,cmd).getStatusCode().value()).isEqualTo(200);
  assertThat(post("/api/comandos",admin,cmd).getStatusCode().value()).isEqualTo(429);
  HttpHeaders h=new HttpHeaders();h.setBearerAuth(edge);
  assertThat(http.exchange("/api/sync/comandos?condominioId=1",HttpMethod.POST,new HttpEntity<>("{}",h),List.class).getBody()).hasSize(1);
  assertThat(http.exchange("/api/sync/comandos?condominioId=1",HttpMethod.POST,new HttpEntity<>("{}",h),List.class).getBody()).isEmpty();
  db.update("UPDATE command SET created=now()-interval '2 minutes'");
  assertThat(post("/api/comandos",admin,cmd).getStatusCode().value()).isEqualTo(200);db.update("UPDATE command SET expires=now()-interval '1 second'");
  assertThat(http.exchange("/api/sync/comandos?condominioId=1",HttpMethod.POST,new HttpEntity<>("{}",h),List.class).getBody()).isEmpty();
 }
 @Test void screenPartialUpdatePreservesConfigAndAlarmCloses(){
  assertThat(post("/api/sync/pantalla",edge,"{\"condominioId\":1,\"cfg\":{\"cor\":[\"Puertas\"]}}").getStatusCode().value()).isEqualTo(200);
  post("/api/sync/pantalla",edge,"{\"condominioId\":1,\"st\":{\"al\":[]}}");
  assertThat(db.queryForObject("SELECT cfg->'cor'->>0 FROM edge_state",String.class)).isEqualTo("Puertas");
  String body="{\"condominioId\":1,\"logs\":[],\"muestras\":[],\"alarmas\":[{\"uid\":\"a-1\",\"sistema\":\"Puertas\",\"detalle\":\"motor\",\"severidad\":2,\"estado\":\"activa\",\"creada\":\"2026-11-08T00:00:00Z\"}]}";
  post("/api/sync/lote",edge,body);post("/api/sync/lote",edge,body.replace("activa","cerrada"));
  assertThat(db.queryForObject("SELECT payload->>'estado' FROM telemetry",String.class)).isEqualTo("cerrada");
 }
 void seedDoor(){
  db.update("INSERT INTO doors VALUES(1,'A','simulated',true,'Test only')");
  db.update("INSERT INTO door_status VALUES(1,'A','cerrada','{\"el\":[0,0,0]}',now())");
 }
 @Test void doorReplayDoesNotDuplicateOrOverwriteNewerState(){
  String body="{\"condominioId\":1,\"alarmas\":[],\"logs\":[],\"muestras\":[],\"puertas\":[{\"uid\":\"door-1\",\"pue\":\"A\",\"nodo\":\"test\",\"puerta\":\"trabada\",\"el\":[0,0,1],\"t\":\"2026-11-08T00:00:00Z\"}]}";
  assertThat(post("/api/sync/lote",edge,body).getStatusCode().value()).isEqualTo(200);
  post("/api/sync/lote",edge,body);
  assertThat(db.queryForObject("SELECT count(*) FROM door_events",Integer.class)).isEqualTo(1);
  post("/api/sync/lote",edge,body.replace("door-1","door-older").replace("trabada","abierta").replace("00:00:00Z","00:00:00Z").replace("2026-11-08","2026-11-07"));
  assertThat(db.queryForObject("SELECT state FROM door_status",String.class)).isEqualTo("trabada");
  assertThat(db.queryForObject("SELECT safety_validated FROM doors",Boolean.class)).isFalse();
 }
 @Test void notificationsAndAcknowledgmentsArePersistentAndIdempotent(){
  String body="{\"condominioId\":1,\"logs\":[],\"muestras\":[],\"alarmas\":[{\"uid\":\"a-notify\",\"sistema\":\"Puertas\",\"detalle\":\"motor\",\"severidad\":2,\"estado\":\"activa\",\"creada\":\"2026-11-08T00:00:00Z\"}]}";
  post("/api/sync/lote",edge,body);post("/api/sync/lote",edge,body);
  assertThat(db.queryForObject("SELECT count(*) FROM notifications",Integer.class)).isEqualTo(1);
  assertThat(post("/api/alarms/a-notify/ack",edge,"{}").getStatusCode().value()).isEqualTo(403);
  post("/api/alarms/a-notify/ack",admin,"{}");post("/api/alarms/a-notify/ack",admin,"{}");
  assertThat(db.queryForObject("SELECT count(*) FROM audit_logs WHERE action='alarm_ack'",Integer.class)).isEqualTo(1);
  long id=db.queryForObject("SELECT id FROM notifications",Long.class);
  post("/api/notifications/"+id+"/read",admin,"{}");post("/api/notifications/"+id+"/read",admin,"{}");
  assertThat(db.queryForObject("SELECT count(*) FROM notification_reads",Integer.class)).isEqualTo(1);
  post("/api/sync/lote",edge,body.replace("activa","cerrada"));
  assertThat(db.queryForObject("SELECT count(*) FROM notifications",Integer.class)).isEqualTo(2);
 }
 @Test void staleDoorAndRevokedValidationBlockCommands(){
  post("/api/sync/latido",edge,"{\"condominioId\":1}");seedDoor();
  db.update("UPDATE door_status SET observed=now()-interval '2 minutes'");
  String cmd="{\"destino\":\"puerta-A\",\"linea\":\"REINICIO\",\"origen\":\"app\",\"confirmed\":true,\"reason\":\"Test only\"}";
  assertThat(post("/api/comandos",admin,cmd).getStatusCode().value()).isEqualTo(409);
  db.update("UPDATE door_status SET observed=now()");
  post("/api/doors/A/safety",admin,"{\"validated\":false,\"evidence\":\"Test revoked\"}");
  assertThat(post("/api/comandos",admin,cmd).getStatusCode().value()).isEqualTo(409);
  assertThat(db.queryForObject("SELECT count(*) FROM command",Integer.class)).isZero();
 }

}
