package com.inventor.atalaya;

import com.fasterxml.jackson.databind.JsonNode;
import java.util.*;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.bind.annotation.*;
import org.springframework.http.HttpStatus;
import org.springframework.web.server.ResponseStatusException;

@RestController
@RequestMapping("/api")
public class Monitoring {
 private final JdbcTemplate db;private final Doors doors;
 public Monitoring(JdbcTemplate db,Doors doors){this.db=db;this.doors=doors;}
 long tenant(){var u=Auth.user();Auth.allow(u.condo(),"ADMIN","VIEWER");return u.condo();}
 @GetMapping("/doors") Object doors(){return doors.list(tenant());}
 @GetMapping("/history") Object history(){return db.queryForList("SELECT date_trunc('day',occurred) AS day,kind,severity,count(*) AS count FROM door_events WHERE condo=? AND occurred>now()-interval '30 days' AND kind<>'contacto' GROUP BY 1,2,3 ORDER BY 1",tenant());}
 @GetMapping("/logs") Object events(@RequestParam(defaultValue="0") int page,@RequestParam(defaultValue="50") int size,@RequestParam(defaultValue="") String door,@RequestParam(defaultValue="") String kind,@RequestParam(defaultValue="-1") int severity){
  Api.require(page>=0&&page<=100000&&size>0&&size<=100&&severity>=-1&&severity<=3);
  return db.queryForList("SELECT id,uid,kind,door_id,severity,occurred,payload::text AS payload FROM door_events WHERE condo=? AND (?='' OR door_id=?) AND (?='' OR kind=?) AND (?=-1 OR severity=?) ORDER BY occurred DESC,id DESC LIMIT ? OFFSET ?",tenant(),door,door,kind,kind,severity,severity,size,(long)page*size);
 }
 @GetMapping("/alarms") Object alarms(){return db.queryForList("SELECT uid,payload::text AS payload,acknowledged_by,acknowledged_at FROM alarms WHERE condo=? ORDER BY (payload->>'creada') DESC LIMIT 200",tenant());}
 @Transactional @PostMapping("/alarms/{uid}/ack") void ack(@PathVariable String uid){var u=Auth.user();Auth.allow(u.condo(),"ADMIN");
  int count=db.update("UPDATE alarms SET acknowledged_by=?,acknowledged_at=now() WHERE condo=? AND uid=? AND acknowledged_at IS NULL AND payload->>'estado'<>'cerrada'",u.email(),u.condo(),uid);
  if(count==1)audit("alarm_ack",uid,"{}");
 }
 @GetMapping("/notifications") Object notifications(){var u=Auth.user();return db.queryForList("SELECT n.id,n.payload::text AS payload,n.created,r.read_at FROM notifications n LEFT JOIN notification_reads r ON r.notification_id=n.id AND r.email=? WHERE n.condo=? ORDER BY n.id DESC LIMIT 100",u.email(),tenant());}
 @PostMapping("/notifications/{id}/read") void read(@PathVariable long id){var u=Auth.user();long c=tenant();db.update("INSERT INTO notification_reads(notification_id,email) SELECT id,? FROM notifications WHERE id=? AND condo=? ON CONFLICT DO NOTHING",u.email(),id,c);}
 @GetMapping("/audit") Object audit(){var u=Auth.user();Auth.allow(u.condo(),"ADMIN");return db.queryForList("SELECT actor,action,target,detail::text,created FROM audit_logs WHERE condo=? ORDER BY id DESC LIMIT 100",u.condo());}
 @GetMapping("/users") Object users(){var u=Auth.user();Auth.allow(u.condo(),"ADMIN");return db.queryForList("SELECT email,role FROM account WHERE condo=? ORDER BY email",u.condo());}
 @Transactional @PostMapping("/doors/{id}/safety") void safety(@PathVariable String id,@RequestBody JsonNode b){var u=Auth.user();Auth.allow(u.condo(),"ADMIN");Api.text(b,"evidence",2000);Api.require(b.path("validated").isBoolean());
  if(db.update("UPDATE doors SET safety_validated=?,safety_evidence=? WHERE condo=? AND id=?",b.path("validated").asBoolean(),b.path("evidence").asText(),u.condo(),id)!=1)throw new ResponseStatusException(HttpStatus.NOT_FOUND);
  audit("physical_validation",id,b.toString());
 }
 void audit(String action,String target,String detail){var u=Auth.user();db.update("INSERT INTO audit_logs(condo,actor,action,target,detail) VALUES(?,?,?,?,?::jsonb)",u.condo(),u.email(),action,target,detail);}
}
