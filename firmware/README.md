# ESP32 / Arduino: compatibilidad de banco

El repositorio original no incluye los sketches de puertas_banco, esp32-nodo o
pantalla Minima: contiene el receptor, simulador y puente USB. No reconstruimos
la lógica de seguridad de motores a partir del protocolo.

`protocol_probe/protocol_probe.ino` es un cliente de diagnóstico sin GPIO ni relés,
compartido por ESP32 y UNO R4 WiFi. Envía cfg/st/log/m con el contrato existente,
procesa HORA/SYNC/ORDEN/REINICIO y muestra órdenes por Serial, sin ejecutarlas.
Copiar secrets.example.h como secrets.h y completar SSID (incluidos espacios),
clave WiFi, IP LAN de Katana y PLACA_TOKEN. secrets.h está ignorado.

Compilar con Arduino CLI:

```
arduino-cli core install arduino:renesas_uno
arduino-cli compile --fqbn arduino:renesas_uno:unor4wifi firmware/protocol_probe
arduino-cli core install esp32:esp32 --additional-urls https://espressif.github.io/arduino-esp32/package_esp32_index.json
arduino-cli compile --fqbn esp32:esp32:esp32 firmware/protocol_probe
```

No flashear sobre firmware operativo sin respaldo. Para Minima conservar el
firmware de pantalla existente y ejecutar edge/puente_pantalla.py con pyserial.
Probar en banco: token incorrecto; reconexión; WiFi sin Katana; mensajes cfg/st;
EL 30–35; desconexión USB; corte WAN; reinicio eléctrico; consumo del outbox;
maniobra segura con sensores reales. Registrar placa, versión y resultado.
