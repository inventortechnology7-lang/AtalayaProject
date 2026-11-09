package com.inventor.katana.auth;
import com.inventor.katana.common.Values;
import com.inventor.katana.users.*;
import com.inventor.katana.audit.AuditService;
import java.security.SecureRandom;
import java.util.*;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.http.HttpStatus;
import org.springframework.web.server.ResponseStatusException;
@Service
public class AuthService {
 public record Principal(String email,String name,String role) {}
 private final JdbcTemplate db;private final UserRepository users;private final UserService service;private final AuditService audit;
 private final String dummy;
 public AuthService(JdbcTemplate db,UserRepository users,UserService service,AuditService audit){this.db=db;this.users=users;this.service=service;this.audit=audit;dummy=service.encode("not-a-real-password");}
 public Principal resolve(String token) { if(token==null||token.length()>128)return null; return db.query("SELECT u.email,u.name,u.role FROM users u JOIN sessions s ON s.user_email=u.email WHERE s.token_hash=? AND s.expires_at>now() AND u.active AND NOT u.reset_required",(r,n)->new Principal(r.getString(1),r.getString(2),r.getString(3)),Values.hash(token)).stream().findFirst().orElse(null); }
 public synchronized String login(String email,String password,String ip) {
  email=UserService.email(email); String key=Values.hash(email),address=Values.hash(ip);
  db.update("DELETE FROM login_attempts WHERE occurred_at<now()-interval '5 minutes'");
  Integer failures=db.queryForObject("SELECT count(*) FROM login_attempts WHERE account_key=? OR address_key=?",Integer.class,key,address);
  if(failures>=5)throw new ResponseStatusException(HttpStatus.TOO_MANY_REQUESTS,"Espera cinco minutos antes de intentar nuevamente");
  var u=users.findById(email).orElse(null);
  boolean ok=service.matches(password,u!=null&&u.passwordHash!=null?u.passwordHash:dummy);
  if(!ok||u==null||!u.active||u.resetRequired){db.update("INSERT INTO login_attempts(account_key,address_key) VALUES(?,?)",key,address);audit.record(email,"login_failed",null);throw new ResponseStatusException(HttpStatus.UNAUTHORIZED,"Credenciales inválidas");}
  byte[] bytes=new byte[32];new SecureRandom().nextBytes(bytes);String token=Base64.getUrlEncoder().withoutPadding().encodeToString(bytes);
  db.update("DELETE FROM sessions WHERE expires_at<now()");db.update("INSERT INTO sessions(token_hash,user_email,expires_at) VALUES(?,?,now()+interval '12 hours')",Values.hash(token),email);audit.record(email,"login",null);return token;
 }
 public void logout(String token) { var p=resolve(token);db.update("DELETE FROM sessions WHERE token_hash=?",Values.hash(token));if(p!=null)audit.record(p.email(),"logout",null); }
}
