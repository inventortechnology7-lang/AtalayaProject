"""Supervise edge workers. Durable data is shared; any worker exit restarts the container."""
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
import receptor
import auth

if not receptor.TOKEN:
    raise SystemExit('PLACA_TOKEN is required')
Path(receptor.DB_RUTA).parent.mkdir(parents=True, exist_ok=True)
receptor.Almacen(receptor.DB_RUTA).db.close()
if not auth.hay_usuarios():
    password = os.environ.get('LOCAL_UI_PASSWORD', '')
    if len(password) < 16:
        raise SystemExit('LOCAL_UI_PASSWORD must have at least 16 characters')
    ok, message = auth.crear(os.environ.get('LOCAL_UI_EMAIL', ''), 'Operador local', 'admin', password)
    if not ok:
        raise SystemExit(message)
children = [subprocess.Popen([sys.executable, '-u', name]) for name in ('receptor.py', 'sync.py', 'ordenes.py', 'ui.py')]

def stop(*args):
    for child in children:
        child.terminate()
    for child in children:
        try:
            child.wait(timeout=10)
        except subprocess.TimeoutExpired:
            child.kill()
    sys.exit(0 if args else 1)

signal.signal(signal.SIGTERM, stop)
signal.signal(signal.SIGINT, stop)
while all(child.poll() is None for child in children):
    time.sleep(1)
stop()
