package com.inventor.katana.events;
import com.inventor.katana.auth.AuthService;
import java.time.Instant;
import java.util.*;
import java.util.concurrent.CopyOnWriteArrayList;
import java.util.concurrent.atomic.AtomicLong;
import org.springframework.http.MediaType;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.transaction.event.*;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;
import org.springframework.web.server.ResponseStatusException;
import org.springframework.http.HttpStatus;
@RestController
public class LiveEvents {
 private record Listener(String token,SseEmitter emitter){}
 private final List<Listener> listeners=new CopyOnWriteArrayList<>();private final AtomicLong revision=new AtomicLong();private final AuthService auth;private long lastSent=-1;private int tick;
 public LiveEvents(AuthService auth){this.auth=auth;}
 @GetMapping(value="/api/local/events",produces=MediaType.TEXT_EVENT_STREAM_VALUE) public synchronized SseEmitter connect(@RequestHeader("Authorization")String bearer){
  if(listeners.size()>=64)throw new ResponseStatusException(HttpStatus.TOO_MANY_REQUESTS,"Demasiadas conexiones SSE");
  SseEmitter emitter=new SseEmitter(3600000L);Listener l=new Listener(bearer.substring(7),emitter);listeners.add(l);
  emitter.onCompletion(()->listeners.remove(l));emitter.onTimeout(()->listeners.remove(l));emitter.onError(e->listeners.remove(l));send(l);return emitter;
 }
 @TransactionalEventListener(phase=TransactionPhase.AFTER_COMMIT) public void change(Changed change){revision.incrementAndGet();}
 private void send(Listener l){try{l.emitter().send(SseEmitter.event().name("state").id(Long.toString(revision.get())).data(Map.of("revision",revision.get(),"at",Instant.now().toString())));}catch(Exception e){listeners.remove(l);l.emitter().complete();}}
 @Scheduled(fixedDelay=2000) public void pulse(){boolean updated=lastSent!=revision.get()||++tick%7==0;lastSent=revision.get();for(var l:listeners){if(auth.resolve(l.token())==null){listeners.remove(l);l.emitter().complete();}else if(updated)send(l);}}
}
