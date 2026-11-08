package com.inventor.katana.common;
import com.fasterxml.jackson.databind.JsonNode;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.time.Instant;
import java.sql.Timestamp;
import java.util.*;
public final class Values {
 private Values() {}
 public static String hash(String raw) { try { return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(raw.getBytes(StandardCharsets.UTF_8))); } catch(Exception e) { throw new IllegalStateException(e); } }
 public static String uid(Object... parts) { return hash(String.join("|",Arrays.stream(parts).map(x->x==null?"None":String.valueOf(x)).toList())).substring(0,32); }
 public static Timestamp at(Instant t) { return Timestamp.from(t); }
 public static Instant time(JsonNode value,Instant fallback) { double seconds=value.asDouble(); if(seconds>1e11)seconds/=1000; if(seconds<1.5e9 || seconds>253402300799d)return fallback; return Instant.ofEpochMilli((long)(seconds*1000)); }
}
