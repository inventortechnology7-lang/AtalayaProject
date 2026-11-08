package com.inventor.atalaya;
import com.fasterxml.jackson.databind.*;
import java.net.URI;
import java.net.http.*;
import java.time.Duration;
import java.util.*;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.web.bind.annotation.*;

/** Persistent Expo delivery; provider acceptance is not device display confirmation. */
@RestController
public class Notifications {
 private final JdbcTemplate db; private final ObjectMapper json; private final boolean enabled;
 private final HttpClient client=HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(5)).build();
 public Notifications(JdbcTemplate db,ObjectMapper json,@Value("${atalaya.push-enabled:false}") boolean enabled){this.db=db;this.json=json;this.enabled=enabled;}
 @PostMapping("/api/push-token") void register(@RequestBody JsonNode b){var u=Auth.user();Auth.allow(u.condo(),"ADMIN","VIEWER");String t=b.path("token").asText();Api.require(t.matches("(?:ExponentPushToken|ExpoPushToken)\\[[A-Za-z0-9_-]{10,200}\\]"));
  db.update("INSERT INTO push_tokens(token,email) VALUES(?,?) ON CONFLICT(token) DO UPDATE SET email=excluded.email,active=true,registered=now()",t,u.email());
 }
 @PostMapping("/api/push-token/remove") void remove(@RequestBody JsonNode b){db.update("UPDATE push_tokens SET active=false WHERE token=? AND email=?",b.path("token").asText(),Auth.user().email());}
 JsonNode post(String endpoint,Object body)throws Exception{
  var request=HttpRequest.newBuilder(URI.create("https://exp.host/--/api/v2/push/"+endpoint)).timeout(Duration.ofSeconds(10)).header("Content-Type","application/json").POST(HttpRequest.BodyPublishers.ofString(json.writeValueAsString(body))).build();
  var r=client.send(request,HttpResponse.BodyHandlers.ofString());if(r.statusCode()!=200)throw new IllegalStateException("Expo HTTP "+r.statusCode());return json.readTree(r.body()).path("data");
 }
 @Scheduled(fixedDelay=30000) void deliver(){
  if(!enabled)return;
  db.update("INSERT INTO push_deliveries(notification_id,token) SELECT n.id,t.token FROM notifications n JOIN account a ON a.condo=n.condo JOIN push_tokens t ON t.email=a.email AND t.active WHERE n.created>=t.registered AND n.created>now()-interval '24 hours' ON CONFLICT DO NOTHING");
  for(var r:db.queryForList("SELECT p.*,n.payload::text FROM push_deliveries p JOIN notifications n ON n.id=p.notification_id JOIN push_tokens t ON t.token=p.token AND t.active WHERE p.status IN ('pending','ticket') AND p.next_attempt<=now() AND p.attempts<8 LIMIT 20")){
   Object id=r.get("notification_id"),token=r.get("token");boolean receipt="ticket".equals(r.get("status"));
   db.update("UPDATE push_deliveries SET attempts=attempts+1,next_attempt=now()+interval '5 minutes' WHERE notification_id=? AND token=?",id,token);
   try{
    JsonNode result;
    if(receipt){result=post("getReceipts",Map.of("ids",List.of(r.get("ticket")))).path(r.get("ticket").toString());if(result.isMissingNode())continue;}
    else{JsonNode p=json.readTree(r.get("payload").toString());result=post("send",Map.of("to",token,"title","ATALAYA · "+p.path("estado").asText(),"body",p.path("detalle").asText("Cambio de alarma"),"data",Map.of("notificationId",id),"sound","default"));}
    if("ok".equals(result.path("status").asText())){db.update("UPDATE push_deliveries SET status=?,ticket=?,error=NULL,next_attempt=now()+interval '15 minutes' WHERE notification_id=? AND token=?",receipt?"provider_accepted":"ticket",receipt?r.get("ticket"):result.path("id").asText(),id,token);}
    else{String code=result.path("details").path("error").asText("provider_error");if(code.equals("DeviceNotRegistered"))db.update("UPDATE push_tokens SET active=false WHERE token=?",token);db.update("UPDATE push_deliveries SET status=?,error=? WHERE notification_id=? AND token=?",code.equals("MessageRateExceeded")?"pending":"failed",code,id,token);}
   }catch(Exception e){db.update("UPDATE push_deliveries SET error=? WHERE notification_id=? AND token=?",e.getClass().getSimpleName(),id,token);}
  }
  db.update("UPDATE push_deliveries SET status='exhausted' WHERE status IN ('pending','ticket') AND attempts>=8");
 }
}
