package com.inventor.katana.monitoring;
import com.inventor.katana.devices.TcpLifecycle;
import com.inventor.katana.doors.DoorService;
import com.inventor.katana.audit.AuditService;
import com.inventor.katana.auth.AuthService;
import jakarta.validation.Valid;
import jakarta.validation.constraints.*;
import java.util.*;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.*;
import org.springframework.transaction.annotation.Transactional;
@RestController
public class MonitoringController {
 public record Settings(@Min(30) @Max(3600) int silenceSeconds){}
 private final JdbcTemplate db;private final TcpLifecycle tcp;private final DoorService doors;private final AuditService audit;
 public MonitoringController(JdbcTemplate db,TcpLifecycle tcp,DoorService doors,AuditService audit){this.db=db;this.tcp=tcp;this.doors=doors;this.audit=audit;}
 @GetMapping("/health") Map<String,Object> health(){db.queryForObject("SELECT 1",Integer.class);if(!tcp.ready())throw new org.springframework.web.server.ResponseStatusException(org.springframework.http.HttpStatus.SERVICE_UNAVAILABLE);return Map.of("status","UP","product","Katana Local");}
 @GetMapping("/api/local/dashboard") Map<String,Object> dashboard(){Map<String,Object> result=new LinkedHashMap<>(db.queryForMap("SELECT (SELECT count(*) FROM devices) AS nodes,(SELECT count(*) FROM devices WHERE connected) AS connected_nodes,(SELECT count(*) FROM alarms WHERE active) AS active_alarms,(SELECT count(*) FROM alarms WHERE active AND severity>=2) AS faults,(SELECT max(last_seen) FROM devices) AS last_contact"));result.put("doors",doors.list());result.put("site","Condominio Las Palmas");result.put("at",java.time.Instant.now());return result;}
 @GetMapping("/api/local/doors") List<Map<String,Object>> doors(){return doors.list();}
 @GetMapping("/api/local/settings") Settings settings(){return new Settings(db.queryForObject("SELECT silence_seconds FROM monitoring_settings WHERE id=1",Integer.class));}
 @PreAuthorize("hasRole('ADMIN')") @Transactional @PutMapping("/api/local/settings") Settings save(@Valid @RequestBody Settings settings,@AuthenticationPrincipal AuthService.Principal actor){db.update("UPDATE monitoring_settings SET silence_seconds=? WHERE id=1",settings.silenceSeconds());audit.record(actor.email(),"monitoring_settings_updated",Integer.toString(settings.silenceSeconds()));return settings;}
}
