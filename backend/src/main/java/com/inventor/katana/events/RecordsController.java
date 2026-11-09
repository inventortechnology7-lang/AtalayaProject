package com.inventor.katana.events;
import com.inventor.katana.common.Queries;
import com.inventor.katana.alarms.AlarmService;
import com.inventor.katana.auth.AuthService;
import java.time.Instant;
import java.util.*;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.*;
@RestController @RequestMapping("/api/local")
public class RecordsController {
 private final Queries queries;private final AlarmService alarms;private final JdbcTemplate db;
 public RecordsController(Queries queries,AlarmService alarms,JdbcTemplate db){this.queries=queries;this.alarms=alarms;this.db=db;}
 @GetMapping("/{resource:logs|alarms|history|telemetry|nodes}") Queries.Page records(@PathVariable String resource,@RequestParam(defaultValue="0") int page,@RequestParam(defaultValue="50")int size,@RequestParam(defaultValue="")String q,@RequestParam(defaultValue="")String door,@RequestParam(defaultValue="")String node,@RequestParam(required=false)Integer severity,@RequestParam(required=false)Instant from,@RequestParam(required=false)Instant to,@RequestParam(required=false)Boolean active){return queries.page(resource,new Queries.Filter(page,size,q,door,node,severity,from,to,active));}
 @PreAuthorize("hasAnyRole('ADMIN','TECNICO')") @PostMapping("/alarms/{uid}/ack") void ack(@PathVariable String uid,@AuthenticationPrincipal AuthService.Principal actor){alarms.acknowledge(uid,actor.email());}
 @GetMapping("/alarms/{uid}/history") List<Map<String,Object>> history(@PathVariable String uid,@RequestParam(defaultValue="0")int page){if(page<0||page>100000)throw new IllegalArgumentException();return db.queryForList("SELECT id,kind,occurred_at,actor,payload::text AS payload FROM alarm_history WHERE alarm_uid=? ORDER BY occurred_at DESC,id DESC LIMIT 50 OFFSET ?",uid,page*50);}
 @PreAuthorize("hasRole('ADMIN')") @GetMapping("/audit") Queries.Page audit(@RequestParam(defaultValue="0")int page){return queries.page("audit",new Queries.Filter(page,50,"","","",null,null,null,null));}
}
