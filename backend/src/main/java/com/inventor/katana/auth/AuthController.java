package com.inventor.katana.auth;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.validation.Valid;
import jakarta.validation.constraints.*;
import java.util.Map;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.*;
@RestController @RequestMapping("/api/local/auth")
public class AuthController {
 public record Login(@Email @NotBlank @Size(max=254) String email,@NotBlank @Size(max=72) String password) {}
 private final AuthService auth;public AuthController(AuthService auth){this.auth=auth;}
 @PostMapping("/login") Map<String,String> login(@Valid @RequestBody Login login,HttpServletRequest request){return Map.of("token",auth.login(login.email(),login.password(),request.getRemoteAddr()));}
 @GetMapping("/me") AuthService.Principal me(@AuthenticationPrincipal AuthService.Principal user){return user;}
 @PostMapping("/logout") void logout(@RequestHeader("Authorization") String bearer){auth.logout(bearer.substring(7));}
}
