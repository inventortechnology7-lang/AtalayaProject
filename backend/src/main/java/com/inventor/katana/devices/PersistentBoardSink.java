package com.inventor.katana.devices;
import com.fasterxml.jackson.databind.*;
import com.inventor.katana.common.Values;
import com.inventor.katana.doors.DoorService;
import com.inventor.katana.alarms.AlarmService;
import com.inventor.katana.events.Changed;
import java.time.Instant;
import java.util.*;
import org.springframework.context.ApplicationEventPublisher;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
@Service
public class PersistentBoardSink implements BoardSink {
 private final JdbcTemplate db;private final ObjectMapper json;private final DoorService doors;private final AlarmService alarms;private final ApplicationEventPublisher events;
 public PersistentBoardSink(JdbcTemplate db,ObjectMapper json,DoorService doors,AlarmService alarms,ApplicationEventPublisher events){this.db=db;this.json=json;this.doors=doors;this.alarms=alarms;this.events=events;}
 @Transactional public void connected(UUID connection,String node,String address,Instant at){
  db.update("INSERT INTO devices(node,address,first_seen,last_seen,connected,current_connection) VALUES(?,?,?,?,true,?) ON CONFLICT(node) DO UPDATE SET address=excluded.address,last_seen=excluded.last_seen,connected=true,current_connection=excluded.current_connection",node,address,Values.at(at),Values.at(at),connection);
  db.update("UPDATE device_connections SET disconnected_at=? WHERE node=? AND disconnected_at IS NULL",Values.at(at),node);
  db.update("INSERT INTO device_connections(id,node,address,connected_at) VALUES(?,?,?,?)",connection,node,address,Values.at(at));events.publishEvent(new Changed("devices"));
 }
 @Transactional public void received(UUID connection,String node,BoardMessage message,Instant at){
  var rows=db.queryForList("SELECT systems::text,current_connection FROM devices WHERE node=? FOR UPDATE",node);
  if(rows.isEmpty()||!connection.equals(rows.getFirst().get("current_connection")))return;
  JsonNode systems;try{systems=json.readTree(rows.getFirst().get("systems").toString());}catch(Exception e){throw new IllegalStateException(e);}
  JsonNode body=message.body();
  if(body.has("cfg")){JsonNode cfg=body.get("cfg");if(cfg.has("cor"))systems=cfg.get("cor");db.update("UPDATE devices SET config=?::jsonb,systems=?::jsonb WHERE node=?",cfg.toString(),systems.toString(),node);}
  db.update("UPDATE devices SET last_seen=? WHERE node=?",Values.at(at),node);
  db.update("UPDATE door_status SET last_contact=? WHERE door_id IN (SELECT id FROM doors WHERE node=?) AND NOT offline",Values.at(at),node);
  if(body.has("st")){JsonNode st=body.get("st");db.update("UPDATE devices SET screen_state=?::jsonb WHERE node=?",st.toString(),node);doors.report(node,st,at);alarms.snapshot(node,systems,st.path("al"),at);}
  if(body.has("logs"))for(JsonNode log:body.get("logs"))log(node,log.get(0),log.get(1).asInt(),log.get(2).asText(),log.get(3).asText(),at);
  if(body.has("log")){JsonNode log=body.get("log");log(node,log.get("t"),log.get("v").asInt(),log.get("s").asText(),log.get("m").asText(),at);}
  if(body.has("m"))for(JsonNode m:body.get("m"))db.update("INSERT INTO telemetry_samples(uid,node,system,magnitude,value,unit,received_at) VALUES(?,?,?,?,?,?,?)",UUID.randomUUID().toString(),node,m.get(0).asText(),m.get(1).asText(),m.get(2).asDouble(),m.get(3).asText(),Values.at(at));
  events.publishEvent(new Changed("state"));
 }
 private void log(String node,JsonNode t,int severity,String system,String message,Instant at){
  String door=message.startsWith("Puerta A")?"A":message.startsWith("Puerta B")?"B":null;
  if(door!=null&&!Boolean.TRUE.equals(db.queryForObject("SELECT EXISTS(SELECT 1 FROM doors WHERE id=?)",Boolean.class,door)))door=null;
  db.update("INSERT INTO system_logs(uid,node,door_id,system,severity,message,occurred_at,received_at,raw_time) VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(uid) DO NOTHING",Values.uid("lg",node,t.asText(),severity,system,message),node,door,system,severity,message,Values.at(Values.time(t,at)),Values.at(at),t.decimalValue());
 }
 @Transactional public void disconnected(UUID connection,String node,Instant at){
  db.update("UPDATE device_connections SET disconnected_at=coalesce(disconnected_at,?) WHERE id=?",Values.at(at),connection);
  if(db.update("UPDATE devices SET connected=false WHERE node=? AND current_connection=?",node,connection)>0)events.publishEvent(new Changed("devices"));
 }
 @Override public List<String> screenLines(){return doors.screenLines();}
 @Transactional public void resetConnections(){db.update("UPDATE device_connections SET disconnected_at=now() WHERE disconnected_at IS NULL");db.update("UPDATE devices SET connected=false,current_connection=NULL");}
}
