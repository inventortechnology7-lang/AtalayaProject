package com.inventor.katana.audit;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
@Service
public class AuditService {
 private final JdbcTemplate db;
 public AuditService(JdbcTemplate db) { this.db=db; }
 public void record(String actor,String action,String target) { db.update("INSERT INTO audit_logs(actor,action,target) VALUES(?,?,?)",actor,action,target); }
}
