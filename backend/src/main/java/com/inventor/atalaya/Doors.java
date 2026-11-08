package com.inventor.atalaya;

import com.fasterxml.jackson.databind.JsonNode;
import java.sql.Timestamp;
import java.time.Instant;
import java.util.*;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;

/** Reported states only. EL fault bits never imply position or safe motion. */
@Service
public class Doors {
 private final JdbcTemplate db;
 public Doors(JdbcTemplate db){this.db=db;}
 static String state(JsonNode n){
  if(n.path("offline").asBoolean())return "sin_comunicacion";
  String raw=n.path("puerta").asText();
  return Set.of("cerrada","abriendo","abierta","cerrando","trabada").contains(raw)?raw:"desconocida";
 }
 void ingest(long condo,JsonNode n){
  Api.text(n,"uid",128);Api.text(n,"nodo",200);Api.timestamp(n,"t");
  String id=n.path("pue").asText();Api.require(Set.of("A","B").contains(id));
  Api.require(n.toString().length()<65536);
  Instant at=Instant.parse(n.path("t").asText());Api.require(!at.isAfter(Instant.now().plusSeconds(60)));
  db.update("INSERT INTO doors(condo,id,node) VALUES(?,?,?) ON CONFLICT(condo,id) DO NOTHING",condo,id,n.path("nodo").asText());
  String state=state(n);
  boolean unchanged=Boolean.TRUE.equals(db.queryForObject("SELECT EXISTS(SELECT 1 FROM door_status WHERE condo=? AND door_id=? AND state=? AND coalesce(raw->'el','null'::jsonb)=?::jsonb)",Boolean.class,condo,id,state,n.has("el")?n.get("el").toString():"null"));
  int added=db.update("INSERT INTO door_events(condo,uid,kind,door_id,severity,occurred,payload) VALUES(?,?,?,?,?,?,?::jsonb) ON CONFLICT DO NOTHING",condo,n.path("uid").asText(),unchanged?"contacto":"estado",id,Set.of("trabada","sin_comunicacion").contains(state)?2:0,Timestamp.from(at),n.toString());
  if(added==0)return;
  int current=db.update("INSERT INTO door_status VALUES(?,?,?,?::jsonb,?) ON CONFLICT(condo,door_id) DO UPDATE SET state=excluded.state,raw=excluded.raw,observed=excluded.observed WHERE excluded.observed>door_status.observed",condo,id,state,n.toString(),Timestamp.from(at));
  // Node reassignment revokes any prior physical validation.
  if(current>0)db.update("UPDATE doors SET node=?,safety_validated=false,safety_evidence=NULL WHERE condo=? AND id=? AND node<>?",n.path("nodo").asText(),condo,id,n.path("nodo").asText());
 }
 List<Map<String,Object>> list(long condo){
  return db.queryForList("SELECT d.*,s.state AS reported_state,s.observed,s.raw::text AS raw,CASE WHEN e.last_seen IS NULL OR e.last_seen<now()-interval '60 seconds' THEN 'edge_sin_enlace' WHEN s.observed<now()-interval '120 seconds' THEN 'sin_comunicacion' ELSE s.state END AS state FROM doors d JOIN door_status s ON s.condo=d.condo AND s.door_id=d.id LEFT JOIN edge_state e ON e.condo=d.condo WHERE d.condo=? ORDER BY d.id",condo);
 }
 boolean safe(long condo,String id){
  return Boolean.TRUE.equals(db.queryForObject("SELECT EXISTS(SELECT 1 FROM doors d JOIN door_status s ON s.condo=d.condo AND s.door_id=d.id WHERE d.condo=? AND d.id=? AND d.safety_validated AND s.observed>now()-interval '45 seconds' AND s.state IN ('cerrada','abierta','trabada') AND s.raw->'el'->>0='0' AND s.raw->'el'->>1='0')",Boolean.class,condo,id));
 }
}
