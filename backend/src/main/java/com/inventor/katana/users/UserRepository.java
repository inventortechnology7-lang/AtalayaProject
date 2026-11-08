package com.inventor.katana.users;
import org.springframework.data.jpa.repository.JpaRepository;
public interface UserRepository extends JpaRepository<LocalUser,String> { long countByRoleAndActiveTrue(String role); }
