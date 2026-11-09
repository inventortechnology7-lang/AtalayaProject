package com.inventor.katana.devices;
import com.inventor.katana.events.Changed;
import com.inventor.katana.users.UserService;
import java.net.InetSocketAddress;
import java.util.*;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.ApplicationArguments;
import org.springframework.boot.ApplicationRunner;
import org.springframework.stereotype.Component;
import org.springframework.transaction.event.*;
import jakarta.annotation.PreDestroy;
@Component
public class TcpLifecycle implements ApplicationRunner {
 private final PersistentBoardSink sink;private final UserService users;private final String bind,token,origins,email,password;private final int port;private final boolean recovery;
 private volatile BoardTcpServer server;
 public TcpLifecycle(PersistentBoardSink sink,UserService users,@Value("${katana.tcp-bind}")String bind,@Value("${katana.tcp-port}")int port,@Value("${katana.token}")String token,@Value("${katana.screen-origins}")String origins,@Value("${katana.admin-email}")String email,@Value("${katana.admin-password}")String password,@Value("${katana.recover-imported-admin}")boolean recovery){this.sink=sink;this.users=users;this.bind=bind;this.port=port;this.token=token;this.origins=origins;this.email=email;this.password=password;this.recovery=recovery;}
 public void run(ApplicationArguments args)throws Exception {users.bootstrap(email,password,recovery);sink.resetConnections();server=new BoardTcpServer(new InetSocketAddress(bind,port),token,sink);server.screenOrigins(new HashSet<>(Arrays.asList(origins.split(","))));server.start();}
 public boolean ready(){return server!=null;}
 public int port(){return server.port();}
 @TransactionalEventListener(phase=TransactionPhase.AFTER_COMMIT) public void changed(Changed event){if(server!=null)server.refreshScreens();}
 @PreDestroy public void close(){if(server!=null){server.close();server=null;}}
}
