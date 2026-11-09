# Katana Local móvil

React Native/Expo, TypeScript estricto. Login y dirección del backend en la pantalla
inicial; resumen, puertas, alarmas, logs e historial paginado. La sesión y caché se
guardan en SecureStore del dispositivo; en la vista web sólo en memoria. Logout
borra la caché. Sin conexión se muestra la fecha del snapshot y no se permite
reconocer alarmas. SSE reconecta y refresca desde PostgreSQL; el polling es respaldo.

```bash
npm ci
npm run export
```

Genera bundles Hermes para Android e iOS en dist/. No es un APK/IPA firmado.
Para instalar una aplicación nativa se requieren SDK Android o Xcode/macOS y las
credenciales de firma correspondientes; no están incluidos en este entorno.

Configurar el origen de la API, por ejemplo `http://192.168.1.20:28080`, sin `/api`.
La laptop debe exponer API_BIND en su IP LAN y el firewall permitir el teléfono.
Por defecto sólo se admite HTTPS. Para una build explícita de LAN de confianza:

```bash
EXPO_PUBLIC_ALLOW_HTTP_LAN=true EXPO_PUBLIC_API_URL=http://192.168.1.20:28080 npm run export
```

El mismo flag debe estar presente al generar/compilar el proyecto nativo para
activar las excepciones de transporte en app.config.js. HTTP envía las credenciales
sin cifrado: usar una LAN aislada de confianza o terminar TLS con certificado
confiable antes de exponer el servicio a otras redes. El transporte por defecto
permanece HTTPS. No hay servidor público, Expo Push ni dependencias de un centro
remoto. Las notificaciones son avisos dentro de la app abierta; fuera de LAN,
suspendida o cerrada no se prometen alertas. Un dispositivo sin conexión sólo
puede consultar su último snapshot; la caché no representa estado actual.
