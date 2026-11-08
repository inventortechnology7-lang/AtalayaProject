# Avance de pruebas de hardware (lo mantiene Negra)

## 2026-11-07
- Enlace Katana↔Negra por Tailscale: directo, 0 % pérdida, 2-100 ms (Katana estaba en la misma LAN). Latido cada 30 s OK.
- Pantalla Atalaya movida a UNO R4 Minima por USB + puente_pantalla.py. Probado contra Negra: /api/placa/1 en vivo (red=3). Falta en Katana (orden #002).
- Siguiente: banco de pruebas de puertas con la R4 WiFi (finales de carrera con pulsadores/reed, PIR HC-SR501, 2 relés, potenciómetro como corriente del motor).
- 2026-11-07 16:30: Katana reenvía la pantalla a Negra por /api/sync/pantalla (verificado en GET /api/placa/1). Falta conectar la Minima a Katana.
- 2026-11-07 17:00: R4 WiFi (firmware puertas_banco, lógica 27/27 pruebas) y ESP32 (esp32-nodo) conectados a "Alexis cell" (R4 172.27.198.129, ESP32 172.27.198.65). Ninguno llega aún a Katana 172.27.198.214:8300: falta abrir ufw y cargar el token de placa (poner_token.sh). Ojo: el SSID real lleva dos espacios al final ("Alexis cell  ").
- 2026-11-07 17:30: firmware puertas_banco único para Puerta A (R4) y Puerta B (ESP32): st con pue/el, logs y magnitudes por puerta. ESP32 probado con SIM (maniobra, sobrecorriente, sensores, bloque). R4: se cuelga tras 2-3 intentos fallidos de conexión mientras el firewall descarta :8300 (problema de WiFiS3); reprobar con el puerto abierto. Pantalla: comando EL + nombres Puerta A/B (compila, falta grabar la Minima). Puente con EL (7 pruebas) publicado (#007). Katana: gestor con login en :8080 y alarmas a pantalla/Negra listos (#006), falta sudo de Alexis.
- 2026-11-07 17:22: token de Katana grabado en R4 y ESP32 (llegó por Taildrop, archivo borrado). Puerta B (ESP32) enlazada con Katana; su alarma llegó a Negra (tabla alarma, sistema Puertas). Puerta A (R4) sigue sin salida por USB ni conexión: pendiente de revisar. Sin hardware conectado: la alarma 'trabada' es esperada.
- 2026-11-07 17:25: Puerta A (R4) regrabada: enlazada con Katana, manda cfg/st/logs y su alarma. Arreglo: esperar el USB al arrancar (while !Serial 4 s). Puertas A y B llegan a Katana.
