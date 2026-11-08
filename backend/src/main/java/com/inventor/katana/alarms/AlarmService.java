package com.inventor.katana.alarms;
import com.fasterxml.jackson.databind.JsonNode;
import com.inventor.katana.common.Values;
import com.inventor.katana.events.Changed;
import com.inventor.katana.audit.AuditService;
import java.time.Instant;
import java.util.*;
import org.springframework.context.ApplicationEventPublisher;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.server.ResponseStatusException;
import org.springframework.http.HttpStatus;
@Service
public class AlarmService {
 private final JdbcTemplate db;private final AuditService audit;private final ApplicationEventPublisher events;
 public AlarmService(JdbcTemplate db,AuditService audit,ApplicationEventPublisher events){this.db=db;this.audit=audit;this.events=events;}
 public void snapshot(String node,JsonNode systems,JsonNode alarms,Instant at){
  Set<String> seen=new HashSet<>();
  for(JsonNode a:alarms){int i=a.get(0).asInt();String system=i<systems.size()?systems.get(i).asText():"sistema"+i;
   String uid=Values.uid("al",node,system,a.get(3).asText(),a.get(4).asText());seen.add(uid);boolean ack=a.get(2).asBoolean()||a.get(2).asInt()==1;
   var old=db.queryForList("SELECT active,board_acknowledged FROM alarms WHERE uid=? FOR UPDATE",uid);
   if(old.isEmpty()){db.update("INSERT INTO alarms(uid,node,system,severity,detail,source,board_acknowledged,opened_at,raw_time) VALUES(?,?,?,?,?,'BOARD',?,?,?)",uid,node,system,a.get(1).asInt(),a.get(4).asText(),ack,Values.at(Values.time(a.get(3),at)),a.get(3).decimalValue());history(uid,"opened",at,null,a.toString());}
   else if(!Boolean.TRUE.equals(old.getFirst().get("active"))||!Objects.equals(old.getFirst().get("board_acknowledged"),ack)){db.update("UPDATE alarms SET active=true,closed_at=NULL,board_acknowledged=? WHERE uid=?",ack,uid);history(uid,"reported",at,null,a.toString());}
  }
  for(var row:db.queryForList("SELECT uid FROM alarms WHERE node=? AND source IN ('BOARD','IMPORT') AND active FOR UPDATE",node))if(!seen.contains(row.get("uid").toString()))close(row.get("uid").toString(),at,"board_cleared");
 }
 public void offline(String node,String door,Instant at){
  if(Boolean.TRUE.equals(db.queryForObject("SELECT EXISTS(SELECT 1 FROM alarms WHERE door_id=? AND source='MONITOR' AND active)",Boolean.class,door)))return;
  String uid=Values.uid("offline",door,at);db.update("INSERT INTO alarms(uid,node,door_id,system,severity,detail,source,opened_at) VALUES(?,?,?,'Puertas',2,?,'MONITOR',?)",uid,node,door,"Puerta "+door+" sin comunicación",Values.at(at));history(uid,"opened",at,null,"{}");
 }
 public void recovered(String door,Instant at){for(var r:db.queryForList("SELECT uid FROM alarms WHERE door_id=? AND source='MONITOR' AND active FOR UPDATE",door))close(r.get("uid").toString(),at,"communication_restored");}
 public void close(String uid,Instant at,String reason){db.update("UPDATE alarms SET active=false,closed_at=? WHERE uid=?",Values.at(at),uid);history(uid,reason,at,null,"{}");}
 public void history(String uid,String kind,Instant at,String actor,String payload){db.update("INSERT INTO alarm_history(alarm_uid,kind,occurred_at,actor,payload) VALUES(?,?,?,?,?::jsonb)",uid,kind,Values.at(at),actor,payload);}
 @Transactional public void acknowledge(String uid,String actor){
  var rows=db.queryForList("SELECT active,acknowledged_at FROM alarms WHERE uid=? FOR UPDATE",uid);if(rows.isEmpty())throw new ResponseStatusException(HttpStatus.NOT_FOUND,"Alarma inexistente");
  if(!Boolean.TRUE.equals(rows.getFirst().get("active")))throw new ResponseStatusException(HttpStatus.CONFLICT,"La alarma está cerrada");
  if(rows.getFirst().get("acknowledged_at")!=null)return;
  db.update("UPDATE alarms SET acknowledged_by=?,acknowledged_at=now() WHERE uid=?",actor,uid);history(uid,"acknowledged",Instant.now(),actor,"{}");audit.record(actor,"alarm_acknowledged",uid);events.publishEvent(new Changed("alarms"));
 }
}
