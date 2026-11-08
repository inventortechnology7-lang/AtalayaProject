#!/usr/bin/env python3
"""Negra simulada SOLO para pruebas (contrato SINCRONIZACION.md): login, latido, lote idempotente."""
import json, sys
from http.server import BaseHTTPRequestHandler, HTTPServer
PUERTO = int(sys.argv[1]) if len(sys.argv) > 1 else 8397
SALIDA = sys.argv[2] if len(sys.argv) > 2 else "/dev/null"
al, lg, mu, lat = {}, set(), set(), []

class H(BaseHTTPRequestHandler):
    def do_POST(self):
        d = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
        if self.path == "/api/login":
            r = {"token": "jwt"} if d.get("correo") and d.get("clave") else None
            if r is None: self.send_response(400); self.end_headers(); return
        elif self.headers.get("Authorization") != "Bearer jwt":
            self.send_response(401); self.end_headers(); return
        elif self.path == "/api/sync/latido":
            lat.append(1); r = {}
        elif self.path == "/api/sync/lote":
            n = a = du = 0
            for x in d["alarmas"]:
                if x["uid"] in al: a += 1
                else: n += 1
                al[x["uid"]] = x["estado"]
            for x in d["logs"]:
                if x["uid"] in lg: du += 1
                else: n += 1; lg.add(x["uid"])
            for x in d["muestras"]:
                if x["uid"] in mu: du += 1
                else: n += 1; mu.add(x["uid"])
            r = {"nuevos": n, "actualizados": a, "duplicados": du}
        else:
            self.send_response(404); self.end_headers(); return
        open(SALIDA, "w").write(json.dumps({"alarmas": al, "logs": len(lg), "muestras": len(mu), "latidos": len(lat)}))
        b = json.dumps(r).encode()
        self.send_response(200); self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)
    def log_message(self, *a): pass
HTTPServer(("127.0.0.1", PUERTO), H).serve_forever()
