#!/usr/bin/env python3
"""Nodo simulado: imita al ESP32 de Puertas. Uso: nodo_simulado.py [host] [puerto]"""
import json, socket, sys, time
from pathlib import Path

host = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1"
puerto = int(sys.argv[2]) if len(sys.argv) > 2 else 8300
token = ""
for l in (Path(__file__).parent / ".env").read_text().splitlines():
    if l.startswith("PLACA_TOKEN="):
        token = l.split("=", 1)[1]

s = socket.create_connection((host, puerto), timeout=5)
f = s.makefile("rwb")
def env(o):
    f.write((o if isinstance(o, str) else json.dumps(o)).encode() + b"\n"); f.flush()

env("TOKEN " + token)
print("<-", f.readline().decode().strip())
now = int(time.time())
env({"cfg": {"cor": ["Camaras", "Puertas"]}})
env({"st": {"al": [[1, 2, 0, now, "Puerta A: motor amperaje alto"]]}})
env({"logs": [[now, 1, "Puertas", "Puerta A abrió"], [now, 2, "Puertas", "Motor A sobrecorriente"]]})
env({"log": {"t": now, "v": 0, "s": "Puertas", "m": "Arranque nodo"}})
env({"m": [["Puertas", "motor_A_amperios", 3.2, "A"], ["Puertas", "energia_V", 12.1, "V"]]})
env("esto no es json")
env({"st": {"al": []}})  # cierra la alarma
time.sleep(0.5)
print("OK enviado")
