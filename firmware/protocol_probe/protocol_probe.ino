// Diagnostic client only. Never operates relays or restarts hardware.
#if defined(ARDUINO_ARCH_ESP32)
#include <WiFi.h>
#else
#include <WiFiS3.h>
#endif
#include "secrets.h"
WiFiClient client;
unsigned long nextConnect = 0, lastSample = 0;
char line[128]; size_t used = 0;
void status() {
  client.println("{\"st\":{\"pue\":\"" DOOR_ID "\",\"puerta\":\"diagnostico\",\"el\":[0,0,0],\"al\":[],\"up\":0}}");
  client.println("{\"m\":[[\"Puertas\",\"diagnostico\",1,\"\"]]}");
}
void setup() { Serial.begin(115200); }
void loop() {
  unsigned long now=millis();
  if ((long)(now-nextConnect)>=0 && !client.connected()) {
    nextConnect=now+10000;
    if(WiFi.status()!=WL_CONNECTED) { WiFi.begin(WIFI_SSID,WIFI_PASSWORD); return; }
    if(client.connect(KATANA_HOST,8300)) {
      used=0;
      client.println("TOKEN " PLACA_TOKEN);
      client.println("{\"cfg\":{\"cor\":[\"Puertas\"]}}");
      client.println("{\"log\":{\"t\":0,\"v\":0,\"s\":\"Puertas\",\"m\":\"Sonda conectada\"}}");
      status();lastSample=now;
    }
  }
  while(client.available()) {
    char c=client.read();
    if(c=='\n') { line[used]=0; Serial.println(line);if(strcmp(line,"SYNC")==0)status();used=0; }
    else if(c!='\r') { if(used<sizeof(line)-1)line[used++]=c;else{client.stop();used=0;break;} }
  }
  if(client.connected() && now-lastSample>=10000) {status();lastSample=now;}
  delay(5);
}
