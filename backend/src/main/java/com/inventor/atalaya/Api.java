package com.inventor.atalaya;

import com.fasterxml.jackson.databind.*;
import java.time.Instant;
import java.util.*;
import java.util.concurrent.CopyOnWriteArrayList;
import org.springframework.http.*;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.server.ResponseStatusException;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

@RestController
public class Api {
 private final JdbcTemplate db; private final ObjectMapper json; private final Doors doors; private final Monitoring monitoring;
 private record Listener(long condo,long expires,SseEmitter emitter){}
 private final List<Listener> listeners=new CopyOnWriteArrayList<>();
 public Api(JdbcTemplate db,ObjectMapper json,Doors doors,Monitoring monitoring){this.db=db;this.json=json;this.doors=doors;this.monitoring=monitoring;}
 static void require(boolean ok){if(!ok)throw new ResponseStatusException(HttpStatus.BAD_REQUEST);}
 static long condo(JsonNode body){require(body.path("condominioId").isIntegralNumber());long c=body.path("condominioId").asLong();require(c>0);return c;}
 static void text(JsonNode n,String key,int max){require(n.path(key).isTextual() && !n.path(key).asText().isBlank() && n.path(key).asText().length()<=max);}
 static void timestamp(JsonNode n,String key){text(n,key,40);try{Instant.parse(n.path(key).asText());}catch(Exception e){require(false);}}
 JsonNode decode(String s){try{return json.readTree(s);}catch(Exception e){throw new IllegalStateException(e);}}
 void heartbeat(long c){db.update("INSERT INTO edge_state(condo) VALUES(?) ON CONFLICT(condo) DO UPDATE SET last_seen=now()",c);}
 @PostMapping("/api/sync/latido") Map<String,Object> beat(@RequestBody JsonNode body){long c=condo(body);Auth.allow(c,"EDGE");heartbeat(c);return Map.of();}
 @Transactional @PostMapping("/api/sync/lote") Map<String,Integer> batch(@RequestBody JsonNode body){
  long c=condo(body);Auth.allow(c,"EDGE");int total=0;
  for(String k:List.of("alarmas","logs","muestras")){require(body.path(k).isArray());total+=body.path(k).size();}require(total<=500);
  int added=0,updated=0,duplicates=0;
  for(String kind:List.of("alarmas","logs","muestras"))for(JsonNode n:body.path(kind)){
   text(n,"uid",128);text(n,"sistema",200);
   if(kind.equals("muestras")){text(n,"magnitud",200);require(n.path("valor").isNumber()&&Double.isFinite(n.path("valor").asDouble()));require(n.path("unidad").isTextual());timestamp(n,"tomada");}
   else{require(n.path("severidad").isIntegralNumber()&&n.path("severidad").asInt()>=0&&n.path("severidad").asInt()<=3);
    if(kind.equals("logs")){require(n.path("mensaje").isTextual());timestamp(n,"t");}
    else {require(n.path("detalle").isTextual());timestamp(n,"creada");require(List.of("activa","reconocida","cerrada").contains(n.path("estado").asText()));if(!n.path("cerradaEn").isMissingNode()&&!n.path("cerradaEn").isNull())timestamp(n,"cerradaEn");}
   }
   require(n.toString().length()<=65536);
   int inserted=db.update("INSERT INTO telemetry(condo,kind,uid,payload) VALUES(?,?,?,?::jsonb) ON CONFLICT DO NOTHING",c,kind,n.path("uid").asText(),n.toString());
   if(inserted==1)added++;
   else if(kind.equals("alarmas")){db.update("UPDATE telemetry SET payload=?::jsonb,received=now() WHERE condo=? AND kind=? AND uid=?",n.toString(),c,kind,n.path("uid").asText());updated++;}else duplicates++;
  }
  if(body.has("puertas")){require(body.path("puertas").isArray()&&body.path("puertas").size()+total<=500);for(JsonNode n:body.path("puertas"))doors.ingest(c,n);}
  heartbeat(c);return Map.of("nuevos",added,"actualizados",updated,"duplicados",duplicates);
 }
 @PostMapping("/api/sync/pantalla") Map<String,Object> screen(@RequestBody JsonNode b){long c=condo(b);Auth.allow(c,"EDGE");require(b.has("cfg")||b.has("st"));require(!b.has("cfg")||b.get("cfg").isObject());require(!b.has("st")||b.get("st").isObject());require(b.toString().length()<=131072);
  db.update("INSERT INTO edge_state(condo,cfg,st) VALUES(?,?::jsonb,?::jsonb) ON CONFLICT(condo) DO UPDATE SET cfg=COALESCE(excluded.cfg,edge_state.cfg),st=COALESCE(excluded.st,edge_state.st),last_seen=now()",c,b.has("cfg")?b.get("cfg").toString():null,b.has("st")?b.get("st").toString():null);return Map.of();}
 @GetMapping("/api/placa/{id}") Map<String,Object> screen(@PathVariable long id){Auth.allow(id,"ADMIN","VIEWER","EDGE");return db.query("SELECT cfg,st,last_seen FROM edge_state WHERE condo=?",(r,n)->{Map<String,Object> m=new LinkedHashMap<>();m.put("cfg",r.getString(1)==null?null:decode(r.getString(1)));m.put("st",r.getString(2)==null?null:decode(r.getString(2)));m.put("ultimoContacto",r.getTimestamp(3).toInstant());return m;},id).stream().findFirst().orElse(Map.of());}
 @GetMapping("/api/dashboard") Map<String,Object> dashboard(){var u=Auth.user();Auth.allow(u.condo(),"ADMIN","VIEWER");Map<String,Object> result=new LinkedHashMap<>();result.put("pantalla",screen(u.condo()));result.put("doors",doors.list(u.condo()));
  for(String k:List.of("alarmas","logs","muestras"))result.put(k,db.query("SELECT payload::text FROM telemetry WHERE condo=? AND kind=? ORDER BY received DESC,uid LIMIT 100",(r,n)->decode(r.getString(1)),u.condo(),k));
  result.put("comandos",db.queryForList("SELECT id,destino,linea,origen,actor,created,consumed,expires,delivery_result,reported FROM command WHERE condo=? ORDER BY id DESC LIMIT 100",u.condo()));return result;}
 @Transactional @PostMapping("/api/comandos") Map<String,Object> command(@RequestBody JsonNode b){var u=Auth.user();Auth.allow(u.condo(),"ADMIN");String destino=b.path("destino").asText(),linea=b.path("linea").asText(),origen=b.path("origen").asText();require(List.of("puerta-A","puerta-B").contains(destino));require(List.of("ORDEN","REINICIO").contains(linea));require(List.of("app","web").contains(origen));
  Boolean online=db.queryForObject("SELECT EXISTS(SELECT 1 FROM edge_state WHERE condo=? AND last_seen>now()-interval '60 seconds')",Boolean.class,u.condo());
  if(!Boolean.TRUE.equals(online))throw new ResponseStatusException(HttpStatus.CONFLICT,"Katana sin enlace reciente");
  // Serialize rate limiting per tenant, including concurrent requests.
  db.queryForList("SELECT condo FROM edge_state WHERE condo=? FOR UPDATE",u.condo());
  if(!b.path("confirmed").asBoolean()||!doors.safe(u.condo(),destino.substring(7)))throw new ResponseStatusException(HttpStatus.CONFLICT,"Seguridad física no validada o estado desconocido");
  text(b,"reason",1000);
  if(Boolean.TRUE.equals(db.queryForObject("SELECT EXISTS(SELECT 1 FROM command WHERE condo=? AND destino=? AND created>now()-interval '60 seconds')",Boolean.class,u.condo(),destino)))throw new ResponseStatusException(HttpStatus.TOO_MANY_REQUESTS,"Espera 60 segundos entre maniobras");
  long id=db.queryForObject("INSERT INTO command(condo,destino,accion,linea,origen,actor) VALUES(?,?,?,?,?,?) RETURNING id",Long.class,u.condo(),destino,linea,linea,origen,u.email());db.update("UPDATE command SET confirmation=? WHERE id=?",b.path("reason").asText(),id);monitoring.audit("command_requested",Long.toString(id),b.toString());notifyCommands(u.condo());return Map.of("id",id,"estado","pendiente");
 }
 @Transactional @PostMapping("/api/sync/comandos") List<Map<String,Object>> consume(@RequestParam long condominioId){Auth.allow(condominioId,"EDGE");return db.queryForList("UPDATE command SET consumed=now() WHERE id IN (SELECT id FROM command WHERE condo=? AND consumed IS NULL AND expires>now() ORDER BY id FOR UPDATE SKIP LOCKED) RETURNING id,destino,accion,linea,origen,expires",condominioId);}
 @GetMapping(value="/api/eventos",produces=MediaType.TEXT_EVENT_STREAM_VALUE) SseEmitter events(){var u=Auth.user();Auth.allow(u.condo(),"EDGE","ADMIN","VIEWER");SseEmitter emitter=new SseEmitter(3600000L);Listener l=new Listener(u.condo(),System.currentTimeMillis()+3600000,emitter);listeners.add(l);emitter.onCompletion(()->listeners.remove(l));emitter.onTimeout(()->listeners.remove(l));emitter.onError(e->listeners.remove(l));send(l,"conectado");return emitter;}
 void send(Listener l,String kind){try{l.emitter().send(SseEmitter.event().data(Map.of("tipo",kind,"condominioId",l.condo())));}catch(Exception e){listeners.remove(l);l.emitter().complete();}}
 void notifyCommands(long c){listeners.stream().filter(l->l.condo()==c).forEach(l->send(l,"comandos"));}
 @Scheduled(fixedDelay=15000) void keepalive(){for(var l:listeners){if(System.currentTimeMillis()>l.expires()){l.emitter().complete();listeners.remove(l);}else{Boolean pending=db.queryForObject("SELECT EXISTS(SELECT 1 FROM command WHERE condo=? AND consumed IS NULL AND expires>now())",Boolean.class,l.condo());send(l,Boolean.TRUE.equals(pending)?"comandos":"actualizacion");}}}
}
