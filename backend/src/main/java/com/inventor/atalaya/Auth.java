package com.inventor.atalaya;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.security.*;
import java.util.*;
import java.util.concurrent.ConcurrentHashMap;
import jakarta.servlet.*;
import jakarta.servlet.http.*;
import jakarta.validation.Valid;
import jakarta.validation.constraints.*;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.ApplicationRunner;
import org.springframework.context.annotation.*;
import org.springframework.http.HttpStatus;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.http.SessionCreationPolicy;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;
import org.springframework.security.web.*;
import org.springframework.security.web.authentication.UsernamePasswordAuthenticationFilter;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.filter.OncePerRequestFilter;
import org.springframework.web.server.ResponseStatusException;

@Configuration
class SecurityConfig {
 @Bean SecurityFilterChain security(HttpSecurity http, Auth auth) throws Exception {
  return http.csrf(c->c.disable()).sessionManagement(c->c.sessionCreationPolicy(SessionCreationPolicy.STATELESS))
   .authorizeHttpRequests(a->a.dispatcherTypeMatchers(DispatcherType.ASYNC, DispatcherType.ERROR).permitAll()
    .requestMatchers("/api/login","/health").permitAll().anyRequest().authenticated())
   .exceptionHandling(e->e.authenticationEntryPoint((q,r,x)->r.sendError(401)))
   .addFilterBefore(new OncePerRequestFilter(){
    protected void doFilterInternal(HttpServletRequest q,HttpServletResponse r,FilterChain c) throws ServletException,IOException {
     if(q.getContentLengthLong()>1048576){r.sendError(413);return;}
     String h=q.getHeader("Authorization");
     if(h!=null && h.startsWith("Bearer ") && h.length()<256){
      var user=auth.resolve(h.substring(7));
      if(user!=null) SecurityContextHolder.getContext().setAuthentication(new UsernamePasswordAuthenticationToken(user,null,List.of(new SimpleGrantedAuthority("ROLE_"+user.role()))));
     }
     c.doFilter(q,r);
    }
   },UsernamePasswordAuthenticationFilter.class).build();
 }
}

@RestController
public class Auth {
 public record User(String email,String role,long condo) {}
 record Login(@NotBlank @Size(max=254) String correo,@NotBlank @Size(max=72) String clave) {}
 private volatile boolean ready;
 private final JdbcTemplate db;
 private final BCryptPasswordEncoder encoder=new BCryptPasswordEncoder(12);
 private final Map<String,Attempt> attempts=new ConcurrentHashMap<>();
 private record Attempt(long start,int count){}
 public Auth(JdbcTemplate db){this.db=db;}
 @Bean ApplicationRunner bootstrap(@Value("${atalaya.admin-email}") String admin,@Value("${atalaya.admin-password}") String password,
 @Value("${atalaya.edge-email}") String edge,@Value("${atalaya.edge-password}") String edgePassword,@Value("${atalaya.condo}") long condo){
  return args->{
   if(admin.equals(edge)||password.length()<16||edgePassword.length()<16||condo<1) throw new IllegalArgumentException("Use distinct accounts and passwords of at least 16 characters");
   for(var a:List.of(new String[]{admin,password,"ADMIN"},new String[]{edge,edgePassword,"EDGE"}))
    db.update("INSERT INTO account VALUES(?,?,?,?) ON CONFLICT(email) DO NOTHING",a[0],encoder.encode(a[1]),a[2],condo);
   ready=true;
  };
 }
 static String hash(String raw){try{return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(raw.getBytes(StandardCharsets.UTF_8)));}catch(NoSuchAlgorithmException e){throw new IllegalStateException(e);}}
 User resolve(String token){
  return db.query("SELECT a.email,a.role,a.condo FROM account a JOIN session_token s ON a.email=s.email WHERE s.hash=? AND s.expires>now()",(r,n)->new User(r.getString(1),r.getString(2),r.getLong(3)),hash(token)).stream().findFirst().orElse(null);
 }
 static User user(){return (User)SecurityContextHolder.getContext().getAuthentication().getPrincipal();}
 static void allow(long condo,String... roles){var u=user();if(u.condo()!=condo || !List.of(roles).contains(u.role()))throw new ResponseStatusException(HttpStatus.FORBIDDEN);}
 @PostMapping("/api/login") Map<String,String> login(@Valid @RequestBody Login body,HttpServletRequest request){
  long now=System.currentTimeMillis();
  attempts.entrySet().removeIf(e->now-e.getValue().start()>60000);
  if(attempts.size()>10000)throw new ResponseStatusException(HttpStatus.TOO_MANY_REQUESTS);
  Attempt a=attempts.compute(request.getRemoteAddr(),(k,v)->v==null?new Attempt(now,1):new Attempt(v.start(),v.count()+1));
  if(a.count()>20)throw new ResponseStatusException(HttpStatus.TOO_MANY_REQUESTS);
  String stored=db.query("SELECT password_hash FROM account WHERE email=?",(r,n)->r.getString(1),body.correo()).stream().findFirst().orElse("$2a$12$abcdefghijklmnopqrstuu0IOrs7Jh1tZlf9QeOoE.nX0gQIdm9S2");
  if(!encoder.matches(body.clave(),stored))throw new ResponseStatusException(HttpStatus.UNAUTHORIZED);
  byte[] bytes=new byte[32];new SecureRandom().nextBytes(bytes);String token=Base64.getUrlEncoder().withoutPadding().encodeToString(bytes);
  db.update("DELETE FROM session_token WHERE expires<now()");
  db.update("INSERT INTO session_token VALUES(?,?,now()+interval '12 hours')",hash(token),body.correo());
  return Map.of("token",token);
 }
 @PostMapping("/api/logout") void logout(@RequestHeader("Authorization") String header){db.update("DELETE FROM session_token WHERE hash=?",hash(header.substring(7)));}
 @GetMapping("/api/me") User me(){return user();}
 @GetMapping("/health") Map<String,String> health(){if(!ready)throw new ResponseStatusException(HttpStatus.SERVICE_UNAVAILABLE);db.queryForObject("SELECT 1",Integer.class);return Map.of("status","UP");}
}
