package com.inventor.atalaya;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;
/** Opt-in retention for derived heartbeat history only; source telemetry and audit never purged. */
@Component
class Retention {
 private final JdbcTemplate db;private final int days;
 Retention(JdbcTemplate db,@Value("${atalaya.contact-retention-days:0}") int days){this.db=db;this.days=days;}
 @Scheduled(fixedDelay=86400000) void prune(){if(days>=30)db.update("DELETE FROM door_events WHERE kind='contacto' AND occurred<now()-(? * interval '1 day')",days);}
}
