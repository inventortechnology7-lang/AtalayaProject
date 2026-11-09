package com.inventor.katana;

import com.fasterxml.jackson.databind.*;
import com.inventor.katana.devices.TcpLifecycle;
import com.inventor.katana.monitoring.MonitoringService;
import java.io.*;
import java.net.*;
import java.net.http.*;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.server.LocalServerPort;
import org.springframework.jdbc.core.JdbcTemplate;
import static org.junit.jupiter.api.Assertions.*;

@SpringBootTest(classes=Application.class,webEnvironment=SpringBootTest.WebEnvironment.RANDOM_PORT)
class LocalIntegrationTest {
 @LocalServerPort int port;
 @Autowired com.inventor.katana.users.UserService users;
 @Autowired JdbcTemplate db; @Autowired TcpLifecycle tcp; @Autowired ObjectMapper json; @Autowired MonitoringService monitoring;
 final HttpClient http=HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(3)).build();
 HttpResponse<String> request(String method,String path,Object body,String token)throws Exception {
  var b=HttpRequest.newBuilder(URI.create("http://localhost:"+port+path)).timeout(Duration.ofSeconds(10));if(token!=null)b.header("Authorization","Bearer "+token);
  b.header("Content-Type","application/json").method(method,body==null?HttpRequest.BodyPublishers.noBody():HttpRequest.BodyPublishers.ofString(json.writeValueAsString(body)));return http.send(b.build(),HttpResponse.BodyHandlers.ofString());
 }
 String login(String email,String password)throws Exception {var r=request("POST","/api/local/auth/login",Map.of("email",email,"password",password),null);assertEquals(200,r.statusCode(),r.body());return json.readTree(r.body()).path("token").asText();}
 void until(java.util.function.BooleanSupplier condition)throws Exception {long end=System.nanoTime()+Duration.ofSeconds(5).toNanos();while(!condition.getAsBoolean()&&System.nanoTime()<end)Thread.sleep(25);assertTrue(condition.getAsBoolean());}
 @Test void localFlowSecurityAndPersistence()throws Exception {
  db.execute("TRUNCATE devices CASCADE");db.execute("TRUNCATE login_attempts");
  assertEquals(401,request("GET","/api/local/dashboard",null,null).statusCode());
  String admin=login("admin@test.local","admin-test-password-123");
  assertEquals(200,request("GET","/health",null,null).statusCode());
  assertEquals(200,request("GET","/api/local/openapi",null,admin).statusCode());
  assertEquals(404,request("POST","/api/sync/latido",Map.of(),admin).statusCode());
  assertEquals(200,request("POST","/api/local/users",Map.of("email","operator@test.local","name","Operador","role","OPERADOR","active",true,"password","operator-password-123"),admin).statusCode());
  String operator=login("operator@test.local","operator-password-123");
  assertEquals(403,request("POST","/api/local/users",Map.of("email","evil@test.local","name","No","role","ADMIN","active",true,"password","some-password-123"),operator).statusCode());
  var streamRequest=HttpRequest.newBuilder(URI.create("http://localhost:"+port+"/api/local/events")).header("Authorization","Bearer "+admin).GET().build();
  var stream=http.send(streamRequest,HttpResponse.BodyHandlers.ofInputStream());assertEquals(200,stream.statusCode());
  try(var input=stream.body()){assertTrue(new BufferedReader(new InputStreamReader(input)).readLine().contains("state"));}
  try(Socket board=new Socket("127.0.0.1",tcp.port())){
   board.setSoTimeout(3000);var out=board.getOutputStream();var in=new BufferedReader(new InputStreamReader(board.getInputStream()));out.write("TOKEN test-board-secret\n".getBytes(StandardCharsets.UTF_8));out.flush();assertTrue(in.readLine().startsWith("HORA "));
   String frame="{\"cfg\":{\"cor\":[\"Puertas\"],\"version\":\"reported-1\"},\"st\":{\"pue\":\"A\",\"puerta\":\"cerrada\",\"el\":[0,1,0],\"up\":10,\"al\":[[0,2,0,1794090000,\"Sensor 2\"]]},\"logs\":[[1794090001,1,\"Puertas\",\"Puerta A aviso\"]],\"m\":[[\"Puertas\",\"voltaje\",12.3,\"V\"]]}\n";
   out.write(frame.getBytes(StandardCharsets.UTF_8));out.flush();until(()->db.queryForObject("SELECT count(*) FROM telemetry_samples",Integer.class)==1);
   var dashboard=json.readTree(request("GET","/api/local/dashboard",null,admin).body());assertEquals(1,dashboard.path("connected_nodes").asInt());assertEquals("cerrada",dashboard.path("doors").get(0).path("state").asText());
   String alarm=db.queryForObject("SELECT uid FROM alarms WHERE active",String.class);
   assertEquals(403,request("POST","/api/local/alarms/"+alarm+"/ack",Map.of(),operator).statusCode());assertEquals(200,request("POST","/api/local/alarms/"+alarm+"/ack",Map.of(),admin).statusCode());
   out.write(frame.getBytes(StandardCharsets.UTF_8));out.flush();until(()->db.queryForObject("SELECT count(*) FROM telemetry_samples",Integer.class)==2);
   assertEquals(1,db.queryForObject("SELECT count(*) FROM system_logs",Integer.class));assertEquals(1,db.queryForObject("SELECT count(*) FROM door_events",Integer.class));
   out.write("{\"st\":{\"pue\":\"B\",\"puerta\":\"abierta\",\"el\":[0,0,0],\"al\":[]}}\n".getBytes(StandardCharsets.UTF_8));out.flush();until(()->db.queryForObject("SELECT count(*) FROM doors",Integer.class)==2);
   assertEquals(0,db.queryForObject("SELECT count(*) FROM alarms WHERE active",Integer.class));
   out.write("{\"st\":{\"pue\":\"A\",\"el\":[0,9,0]},\"log\":{\"t\":1,\"v\":0,\"s\":\"bad\",\"m\":\"must rollback\"}}\n".getBytes(StandardCharsets.UTF_8));out.flush();
   Thread.sleep(100);assertEquals(1,db.queryForObject("SELECT count(*) FROM system_logs",Integer.class));
   var logs=json.readTree(request("GET","/api/local/logs?door=A&severity=1&q=aviso&size=1",null,operator).body());assertEquals(1,logs.path("total").asInt());
  }
  until(()->db.queryForObject("SELECT count(*) FROM devices WHERE connected",Integer.class)==0);
  db.update("UPDATE door_status SET last_contact=now()-interval '121 seconds'");monitoring.check();
  assertEquals(2,db.queryForObject("SELECT count(*) FROM alarms WHERE active AND source='MONITOR'",Integer.class));
  var offline=json.readTree(request("GET","/api/local/doors",null,operator).body());assertTrue(offline.get(0).path("unavailable").asBoolean());assertEquals(0,offline.get(0).path("sensor_1").asInt());
  assertEquals(200,request("POST","/api/local/auth/logout",Map.of(),operator).statusCode());assertEquals(401,request("GET","/api/local/dashboard",null,operator).statusCode());
  assertEquals(400,request("PUT","/api/local/settings",Map.of("silenceSeconds",1),admin).statusCode());
  for(int i=0;i<5;i++)assertEquals(401,request("POST","/api/local/auth/login",Map.of("email","nobody@test.local","password","bad-password"),null).statusCode());
  assertEquals(429,request("POST","/api/local/auth/login",Map.of("email","nobody@test.local","password","bad-password"),null).statusCode());
 }
 @Test void importedAdminResetIsOneTimeAndAudited()throws Exception {
  String email="imported@test.local";
  db.update("INSERT INTO users(email,name,role,active,reset_required) VALUES(?,'Imported','ADMIN',true,true)",email);
  users.bootstrap(email,"recovered-password-123",true);
  assertEquals(200,request("GET","/api/local/auth/me",null,login(email,"recovered-password-123")).statusCode());
  assertEquals(1,db.queryForObject("SELECT count(*) FROM audit_logs WHERE actor=? AND action='imported_admin_recovered'",Integer.class,email));
  assertThrows(IllegalArgumentException.class,()->users.bootstrap(email,"another-password-123",true));
 }

}
