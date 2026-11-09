package com.inventor.katana.users;
import jakarta.persistence.*;
import java.time.Instant;
@Entity @Table(name="users")
public class LocalUser {
 @Id @Column(length=254) public String email;
 @Column(nullable=false,length=200) public String name;
 @Column(nullable=false,length=16) public String role;
 @Column(name="password_hash",length=100) public String passwordHash;
 public boolean active=true;
 @Column(name="reset_required") public boolean resetRequired;
 @Column(name="created_at") public Instant createdAt=Instant.now();
 public LocalUser() {}
 public record View(String email,String name,String role,boolean active,boolean resetRequired,Instant createdAt) {}
 public View view() { return new View(email,name,role,active,resetRequired,createdAt); }
}
