package com.inventor.katana.doors;
import com.fasterxml.jackson.databind.JsonNode;
import com.inventor.katana.common.Values;
import com.inventor.katana.alarms.AlarmService;
import java.time.Instant;
import java.util.*;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
@Service
public class DoorService {
 private final JdbcTemplate db;private final AlarmService alarms;
 public DoorService(JdbcTemplate db,AlarmService alarms){this.db=db;this.alarms=alarms;}
 public void report(String node,JsonNode st,Instant at){
  String door=st.path("pue").asText().toUpperCase(Locale.ROOT);if(!Set.of("A","B").contains(door))return;
  db.update("INSERT INTO doors(id,node) VALUES(?,?) ON CONFLICT(id) DO UPDATE SET node=excluded.node",door,node);
  var previous=db.queryForList("SELECT * FROM door_status WHERE door_id=? FOR UPDATE",door);
  Map<String,Object> old=previous.isEmpty()?Map.of():previous.getFirst();
  String state=st.hasNonNull("puerta")?st.get("puerta").asText():(String)old.get("reported_state");
  Object s1=st.hasNonNull("el")?st.get("el").get(0).asInt():old.get("sensor_1"),s2=st.hasNonNull("el")?st.get("el").get(1).asInt():old.get("sensor_2"),motor=st.hasNonNull("el")?st.get("el").get(2).asInt():old.get("motor");
  Object uptime=st.hasNonNull("up")?st.get("up").asLong():old.get("uptime");
  boolean changed=old.isEmpty()||Boolean.TRUE.equals(old.get("offline"))||!Objects.equals(state,old.get("reported_state"))||!Objects.equals(s1,old.get("sensor_1"))||!Objects.equals(s2,old.get("sensor_2"))||!Objects.equals(motor,old.get("motor"));
  db.update("INSERT INTO door_status(door_id,reported_state,sensor_1,sensor_2,motor,uptime,observed_at,last_contact,offline) VALUES(?,?,?,?,?,?,?,?,false) ON CONFLICT(door_id) DO UPDATE SET reported_state=excluded.reported_state,sensor_1=excluded.sensor_1,sensor_2=excluded.sensor_2,motor=excluded.motor,uptime=excluded.uptime,observed_at=excluded.observed_at,last_contact=excluded.last_contact,offline=false",door,state,s1,s2,motor,uptime,Values.at(at),Values.at(at));
  if(changed)event(door,node,Boolean.TRUE.equals(old.get("offline"))?"reconnected":"state",0,at,st.toString());alarms.recovered(door,at);
 }
 public void event(String door,String node,String kind,int severity,Instant at,String payload){db.update("INSERT INTO door_events(uid,door_id,node,kind,severity,occurred_at,payload) VALUES(?,?,?,?,?,?,?::jsonb) ON CONFLICT DO NOTHING",Values.uid("door",door,node,at,kind),door,node,kind,severity,Values.at(at),payload);}
 public List<Map<String,Object>> list(){return db.queryForList("SELECT d.id,d.node,s.*,CASE WHEN s.offline OR NOT n.connected THEN 'sin comunicación' ELSE coalesce(s.reported_state,'sin datos') END AS state,(s.offline OR NOT n.connected) AS unavailable FROM doors d JOIN door_status s ON s.door_id=d.id JOIN devices n ON n.node=d.node ORDER BY d.id");}
 public List<String> screenLines(){List<String> result=new ArrayList<>();for(var row:list()){int start=row.get("id").equals("A")?30:33;int i=0;for(String key:List.of("sensor_1","sensor_2","motor")){Object value=row.get(key);if(Boolean.TRUE.equals(row.get("unavailable")))value=1;if(value!=null)result.add("EL "+(start+i)+" "+value);i++;}}return result;}
}
