package com.inventor.katana.config;
import com.inventor.katana.auth.AuthService;
import jakarta.servlet.*;
import jakarta.servlet.http.*;
import java.io.IOException;
import java.util.List;
import org.springframework.context.annotation.*;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.config.annotation.method.configuration.EnableMethodSecurity;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.http.SessionCreationPolicy;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.web.*;
import org.springframework.security.web.authentication.UsernamePasswordAuthenticationFilter;
import org.springframework.web.filter.OncePerRequestFilter;
@Configuration @EnableMethodSecurity
public class SecurityConfig {
 @Bean SecurityFilterChain security(HttpSecurity http,AuthService auth)throws Exception {
  return http.csrf(c->c.disable()).sessionManagement(c->c.sessionCreationPolicy(SessionCreationPolicy.STATELESS))
   .authorizeHttpRequests(a->a.dispatcherTypeMatchers(DispatcherType.ASYNC,DispatcherType.ERROR).permitAll().requestMatchers("/health","/api/local/auth/login").permitAll().anyRequest().authenticated())
   .exceptionHandling(e->e.authenticationEntryPoint((q,r,x)->r.sendError(401)))
   .addFilterBefore(new OncePerRequestFilter(){protected void doFilterInternal(HttpServletRequest q,HttpServletResponse r,FilterChain chain)throws IOException,ServletException {
    if(q.getContentLengthLong()>65536){r.sendError(413);return;}
    String h=q.getHeader("Authorization");if(h!=null&&h.startsWith("Bearer ")){var p=auth.resolve(h.substring(7));if(p!=null)SecurityContextHolder.getContext().setAuthentication(new UsernamePasswordAuthenticationToken(p,null,List.of(new SimpleGrantedAuthority("ROLE_"+p.role()))));}
    chain.doFilter(q,r);
   }},UsernamePasswordAuthenticationFilter.class).build();
 }
}
