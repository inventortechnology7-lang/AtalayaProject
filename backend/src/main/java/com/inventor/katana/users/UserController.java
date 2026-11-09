package com.inventor.katana.users;
import com.inventor.katana.auth.AuthService;
import com.inventor.katana.audit.AuditService;
import jakarta.validation.Valid;
import java.util.*;
import org.springframework.data.domain.*;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.*;
@RestController @RequestMapping("/api/local")
public class UserController {
 private final UserRepository users;private final UserService service;private final JdbcTemplate db;private final AuditService audit;
 public UserController(UserRepository users,UserService service,JdbcTemplate db,AuditService audit){this.users=users;this.service=service;this.db=db;this.audit=audit;}
 @PreAuthorize("hasRole('ADMIN')") @GetMapping("/users") Page<LocalUser.View> list(@RequestParam(defaultValue="0") int page){if(page<0||page>100000)throw new IllegalArgumentException();return users.findAll(PageRequest.of(page,50,Sort.by("email"))).map(LocalUser::view);}
 @PreAuthorize("hasRole('ADMIN')") @PostMapping("/users") LocalUser.View save(@Valid @RequestBody UserService.Edit edit,@AuthenticationPrincipal AuthService.Principal actor){return service.save(edit,actor.email());}
 @GetMapping("/sessions") List<Map<String,Object>> sessions(@AuthenticationPrincipal AuthService.Principal user){return db.queryForList("SELECT id,user_email,created_at,expires_at FROM sessions WHERE expires_at>now() AND (? OR user_email=?) ORDER BY created_at DESC LIMIT 100",user.role().equals("ADMIN"),user.email());}
 @DeleteMapping("/sessions/{id}") void revoke(@PathVariable UUID id,@AuthenticationPrincipal AuthService.Principal user){db.update("DELETE FROM sessions WHERE id=? AND (? OR user_email=?)",id,user.role().equals("ADMIN"),user.email());audit.record(user.email(),"session_revoked",id.toString());}
}
