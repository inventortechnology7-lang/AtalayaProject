package com.inventor.katana.common;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.sql.Timestamp;
import java.time.Instant;
import java.util.*;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
@Service
public class Queries {
 public record Page(List<Map<String,Object>> content,long total,int page,int size){}
 public record Filter(int page,int size,String q,String door,String node,Integer severity,Instant from,Instant to,Boolean active){public Filter{if(page<0||page>100000||size<1||size>100||q.length()>200||node.length()>200||!Set.of("","A","B").contains(door)||severity!=null&&(severity<0||severity>3)||from!=null&&to!=null&&from.isAfter(to))throw new IllegalArgumentException();}}
 private final JdbcTemplate db;private final ObjectMapper json;
 public Queries(JdbcTemplate db,ObjectMapper json){this.db=db;this.json=json;}
 public Page page(String resource,Filter f){
  String table,time,text;boolean door=true,node=true,severity=true;
  switch(resource){
   case "logs" -> {table="system_logs";time="occurred_at";text="message || ' ' || system";}
   case "alarms" -> {table="alarms";time="opened_at";text="detail || ' ' || system";}
   case "history" -> {table="door_events";time="occurred_at";text="kind || ' ' || payload::text";}
   case "telemetry" -> {table="telemetry_samples";time="received_at";text="system || ' ' || magnitude";door=false;severity=false;}
   case "nodes" -> {table="devices";time="last_seen";text="node || ' ' || coalesce(address,'') || ' ' || systems::text";door=false;severity=false;}
   case "audit" -> {table="audit_logs";time="occurred_at";text="action || ' ' || coalesce(actor,'')";door=false;node=false;severity=false;}
   default -> throw new IllegalArgumentException();
  }
  StringBuilder where=new StringBuilder(" WHERE true");List<Object> args=new ArrayList<>();
  if(!f.q().isEmpty()){where.append(" AND position(lower(?) in lower("+text+"))>0");args.add(f.q());}
  if(door&&!f.door().isEmpty()){where.append(" AND door_id=?");args.add(f.door());}
  if(node&&!f.node().isEmpty()){where.append(" AND node=?");args.add(f.node());}
  if(severity&&f.severity()!=null){where.append(" AND severity=?");args.add(f.severity());}
  if(f.from()!=null){where.append(" AND "+time+">=?");args.add(Timestamp.from(f.from()));}
  if(f.to()!=null){where.append(" AND "+time+"<=?");args.add(Timestamp.from(f.to()));}
  if(resource.equals("alarms")&&f.active()!=null){where.append(" AND active=?");args.add(f.active());}
  long total=db.queryForObject("SELECT count(*) FROM "+table+where,Long.class,args.toArray());
  String key=resource.equals("nodes")?"node":resource.equals("audit")?"id":"uid";
  args.add(f.size());args.add(f.page()*f.size());
  var rows=db.queryForList("SELECT * FROM "+table+where+" ORDER BY "+time+" DESC,"+key+" LIMIT ? OFFSET ?",args.toArray());
  for(var row:rows)for(String field:List.of("payload","systems","config","screen_state","detail")){Object v=row.get(field);if(v!=null&&v.getClass().getName().equals("org.postgresql.util.PGobject"))try{row.put(field,json.readTree(v.toString()));}catch(Exception e){throw new IllegalStateException(e);}}
  return new Page(rows,total,f.page(),f.size());
 }
}
