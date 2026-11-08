package com.inventor.katana.users;
import com.inventor.katana.audit.AuditService;
import jakarta.validation.constraints.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;
import org.springframework.web.server.ResponseStatusException;
import org.springframework.http.HttpStatus;
@Service
public class UserService {
 public record Edit(@Email @NotBlank @Size(max=254) String email,@NotBlank @Size(max=200) String name,@Pattern(regexp="ADMIN|TECNICO|OPERADOR") @NotNull String role,boolean active,@Size(max=72) String password) {}
 private final UserRepository users; private final JdbcTemplate db; private final AuditService audit;
 private final BCryptPasswordEncoder encoder=new BCryptPasswordEncoder(12);
 public UserService(UserRepository users,JdbcTemplate db,AuditService audit) { this.users=users;this.db=db;this.audit=audit; }
 public boolean matches(String password,String hash){return encoder.matches(password,hash);}
 public static String email(String value) { return value.strip().toLowerCase(Locale.ROOT); }
 public String encode(String value) { if(value==null||value.length()<12||value.getBytes(StandardCharsets.UTF_8).length>72) throw new IllegalArgumentException("password_length");return encoder.encode(value); }
 @Transactional public LocalUser.View save(Edit edit,String actor) {
  db.queryForList("SELECT pg_advisory_xact_lock(8300,2)");
  String email=email(edit.email()); LocalUser u=users.findById(email).orElseGet(LocalUser::new);
  if("ADMIN".equals(u.role)&&u.active&&(!edit.active()||!"ADMIN".equals(edit.role()))&&users.countByRoleAndActiveTrue("ADMIN")<=1)throw new ResponseStatusException(HttpStatus.CONFLICT,"Debe permanecer un administrador activo");
  boolean created=u.email==null;u.email=email;u.name=edit.name().strip();u.role=edit.role();u.active=edit.active();
  if(edit.password()!=null&&!edit.password().isEmpty()){u.passwordHash=encode(edit.password());u.resetRequired=false;}
  if(u.passwordHash==null)throw new IllegalArgumentException("password_required");
  users.saveAndFlush(u); db.update("DELETE FROM sessions WHERE user_email=?",email);
  audit.record(actor,created?"user_created":"user_updated",email); return u.view();
 }
 @Transactional public void bootstrap(String email,String password,boolean recovery) {
  if(email.isBlank()||password.isBlank())return;
  email=email(email);
  if(users.count()==0){LocalUser u=new LocalUser();u.email=email;u.name="Administrador local";u.role="ADMIN";u.passwordHash=encode(password);users.saveAndFlush(u);audit.record(email,"bootstrap",email);}
  else if(recovery){LocalUser u=users.findById(email).orElseThrow();if(!"ADMIN".equals(u.role)||!u.resetRequired)throw new IllegalArgumentException("Recovery restricted to imported admin");u.passwordHash=encode(password);u.active=true;u.resetRequired=false;users.saveAndFlush(u);db.update("DELETE FROM sessions WHERE user_email=?",email);audit.record(email,"imported_admin_recovered",email);}
 }
}
