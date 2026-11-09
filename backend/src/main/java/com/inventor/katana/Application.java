package com.inventor.katana;
import java.util.Arrays;
import org.flywaydb.core.Flyway;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.scheduling.annotation.EnableScheduling;
@SpringBootApplication @EnableScheduling
public class Application {
 public static void main(String[] args) {
  // Offline preparation: schema only, no users, HTTP, TCP or scheduled writers.
  if(Arrays.asList(args).contains("--migrate-only")) {
   Flyway.configure().dataSource(System.getenv("DB_URL"),System.getenv().getOrDefault("DB_USER","katana"),System.getenv("DB_PASSWORD"))
    .locations("classpath:db/katana").load().migrate();
   return;
  }
  SpringApplication.run(Application.class,args);
 }
}
