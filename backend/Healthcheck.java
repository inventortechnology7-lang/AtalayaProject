import java.net.URI;
import java.net.http.*;
import java.time.Duration;
public class Healthcheck {
 public static void main(String[] args)throws Exception { var request=HttpRequest.newBuilder(URI.create("http://127.0.0.1:8080/health")).timeout(Duration.ofSeconds(3)).GET().build();if(HttpClient.newHttpClient().send(request,HttpResponse.BodyHandlers.discarding()).statusCode()!=200)System.exit(1); }
}
