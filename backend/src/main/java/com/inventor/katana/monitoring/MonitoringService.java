package com.inventor.katana.monitoring;
import com.inventor.katana.alarms.AlarmService;
import com.inventor.katana.doors.DoorService;
import com.inventor.katana.events.Changed;
import com.inventor.katana.common.Values;
import java.time.Instant;
import org.springframework.context.ApplicationEventPublisher;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
@Service
public class MonitoringService {
 private final JdbcTemplate db;private final AlarmService alarms;private final DoorService doors;private final ApplicationEventPublisher events;
 public MonitoringService(JdbcTemplate db,AlarmService alarms,DoorService doors,ApplicationEventPublisher events){this.db=db;this.alarms=alarms;this.doors=doors;this.events=events;}
 @Scheduled(fixedDelay=10000) @Transactional public void check(){
  int seconds=db.queryForObject("SELECT silence_seconds FROM monitoring_settings WHERE id=1",Integer.class);Instant now=Instant.now();
  for(var r:db.queryForList("SELECT s.door_id,d.node FROM door_status s JOIN doors d ON d.id=s.door_id WHERE NOT s.offline AND s.last_contact<? FOR UPDATE OF s",Values.at(now.minusSeconds(seconds)))){
   String door=r.get("door_id").toString(),node=r.get("node").toString();db.update("UPDATE door_status SET offline=true WHERE door_id=?",door);alarms.offline(node,door,now);doors.event(door,node,"disconnected",2,now,"{}");db.update("INSERT INTO system_logs(uid,node,door_id,system,severity,message,occurred_at) VALUES(?,?,?,'Puertas',2,?,?)",Values.uid("offline-log",door,now),node,door,"Puerta "+door+" sin comunicación",Values.at(now));events.publishEvent(new Changed("offline"));
  }
 }
}
