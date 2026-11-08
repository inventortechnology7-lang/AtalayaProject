#!/usr/bin/env python3
"""Órdenes remotas Negra -> Katana -> placa de la puerta (orden #009, versión SSE).
Deja UNA conexión en vivo a Negra (GET /api/eventos, text/event-stream). Solo cuando llega
{"tipo":"comandos"} (y una vez al conectar) pide POST /api/sync/comandos, guarda cada orden en
ordenes_aplicativo / ordenes_web (+ carpetas ordenes-aplicativo/ y ordenes-web/) y se la pasa al
receptor por su socket local, que la manda a la placa y registra el log (va a Negra en el lote).
Sin consultas periódicas."""
import hashlib, json, logging, socket, sqlite3, sys, time, urllib.error, urllib.request
from pathlib import Path

BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE))          # el servicio corre con python3 -I
import sync                            # reutiliza .env, login y JWT de sync.py

DB = sync.DB
SOCK = sync.ENV.get("ORDENES_SOCK", str(BASE / "ordenes.sock"))
RUTA_EVENTOS = sync.ENV.get("RUTA_EVENTOS", "/api/eventos")
RUTA_COMANDOS = sync.ENV.get("RUTA_COMANDOS", "/api/sync/comandos")
SSE_SILENCIO_S = float(sync.ENV.get("SSE_SILENCIO_S", "600"))   # sin nada en 10 min => reconectar
TABLA = {"app": "ordenes_aplicativo", "web": "ordenes_web"}
CARPETA = {"app": "ordenes-aplicativo", "web": "ordenes-web"}
LINEAS = {"REINICIO", "ORDEN"}
log = logging.getLogger("ordenes")

SCHEMA = "".join(f"""CREATE TABLE IF NOT EXISTS {t}(id INTEGER PRIMARY KEY, destino TEXT, accion TEXT, linea TEXT,
  recibida REAL, estado TEXT DEFAULT 'pendiente', resultado TEXT, entregada REAL, crudo TEXT);""" for t in TABLA.values())


def abrir_db():
    db = sqlite3.connect(DB, timeout=10)
    db.executescript(SCHEMA)
    return db


def al_receptor(pue, linea, origen, oid=""):
    """-> (ok, texto). Si el receptor no responde, ok=None (se reintenta luego)."""
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
            s.settimeout(10)
            s.connect(SOCK)
            s.sendall(f"ORDEN {pue} {linea} {origen} {oid}".rstrip().encode() + b"\n")
            r = s.makefile().readline().strip()
        return r.startswith("OK"), r[3:]
    except OSError as e:
        return None, f"receptor sin respuesta: {e}"


def guardar(db, o):
    origen = o.get("origen") if o.get("origen") in TABLA else "web"
    t = TABLA[origen]
    db.execute(f"INSERT OR IGNORE INTO {t}(id,destino,accion,linea,recibida,crudo) VALUES(?,?,?,?,?,?)",
               (o.get("id"), o.get("destino"), o.get("accion"), o.get("linea"), time.time(), json.dumps(o, ensure_ascii=False)))
    db.commit()
    d = Path(sync.ENV.get("ORDENES_DIR", str(BASE))) / CARPETA[origen]
    d.mkdir(exist_ok=True)
    with open(d / time.strftime("%Y-%m-%d.jsonl"), "a") as f:
        f.write(json.dumps(dict(o, recibida=time.strftime("%Y-%m-%d %H:%M:%S")), ensure_ascii=False) + "\n")


def log_local(db, msg):
    """Log sev 2 directo en la base (+ outbox para Negra) cuando el receptor no está."""
    t = time.time()
    uid = hashlib.sha256(f"lg|katana|{t}|2|Puertas|{msg}".encode()).hexdigest()[:32]
    db.execute("INSERT OR IGNORE INTO logs VALUES(?,?,?,?,?,?)", (uid, "katana", t, 2, "Puertas", msg))
    db.execute("INSERT OR IGNORE INTO outbox(uid,tipo,payload,creado) VALUES(?,?,?,?)", (uid, "log", json.dumps(
        dict(uid=uid, nodo="katana", t=t, sev=2, sistema="Puertas", msg=msg)), t))


def entregar_pendientes(db):
    for origen, t in TABLA.items():
        for oid, destino, linea in db.execute(f"SELECT id,destino,linea FROM {t} WHERE estado='pendiente' ORDER BY id").fetchall():
            pue = str(destino or "").replace("puerta-", "").upper()
            # Claim before network IO: after a crash an uncertain physical command is never replayed.
            db.execute(f"UPDATE {t} SET estado='incierta', resultado='entrega iniciada; sin confirmacion fisica' WHERE id=?", (oid,))
            db.commit()
            if pue not in ("A", "B") or linea not in LINEAS:
                ok, txt = False, f"orden inválida: destino={destino} linea={linea}"
            else:
                ok, txt = al_receptor(pue, linea, origen, str(oid))
            if ok is None:      # no se reintenta luego: una orden física atrasada es peligrosa
                ok, txt = False, f"Orden remota {linea} ({'aplicativo' if origen == 'app' else 'web'}) #{oid} no entregada a Puerta {pue}: receptor caído"
                log_local(db, txt)
            db.execute(f"UPDATE {t} SET estado=?, resultado=?, entregada=? WHERE id=?",
                       ("entregada" if ok else "no entregada", txt, time.time(), oid))
            db.commit()
            log.info("orden %s (%s): %s", oid, origen, txt)


def traer_comandos(enlace, db):
    lista = enlace._post(f"{RUTA_COMANDOS}?condominioId={sync.CONDO_ID}", {})
    for o in lista if isinstance(lista, list) else []:
        guardar(db, o)          # primero a disco: Negra ya las marcó entregadas
    entregar_pendientes(db)


def escuchar(enlace, db):
    """Abre la SSE; vuelve (o lanza) cuando se corta."""
    if not enlace.jwt or time.time() - enlace.jwt_t > 11 * 3600:
        enlace.login()
    req = urllib.request.Request(sync.URL + RUTA_EVENTOS, headers={
        "Authorization": "Bearer " + enlace.jwt, "Accept": "text/event-stream", "Cache-Control": "no-cache"})
    try:
        r = urllib.request.urlopen(req, timeout=SSE_SILENCIO_S)
    except urllib.error.HTTPError as e:
        if e.code == 401:
            enlace.jwt = None
        raise
    with r:
        log.info("conectado a eventos de Negra")
        traer_comandos(enlace, db)      # por si quedó algo pendiente
        datos = []
        for crudo in r:
            l = crudo.decode("utf-8", "replace").rstrip("\r\n")
            if l.startswith("data:"):
                datos.append(l[5:].strip())
            elif l == "" and datos:
                try:
                    ev = json.loads("\n".join(datos))
                except ValueError:
                    ev = {}
                datos = []
                if isinstance(ev, dict) and ev.get("tipo") == "comandos" and int(ev.get("condominioId", sync.CONDO_ID)) == sync.CONDO_ID:
                    traer_comandos(enlace, db)
            if time.time() - enlace.jwt_t > 11 * 3600:
                return                          # renovar JWT reconectando
    log.warning("Negra cerró la conexión de eventos")


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    if not (sync.URL and sync.USUARIO and sync.CLAVE):
        raise SystemExit("Falta NEGRA_URL / SYNC_USUARIO / SYNC_CLAVE en .env")
    enlace, espera = sync.Enlace(), 1
    while True:
        db = None
        try:
            db = abrir_db()
            entregar_pendientes(db)
            t0 = time.time()
            escuchar(enlace, db)
            espera = 1 if time.time() - t0 > 60 else espera
        except Exception as e:
            log.warning("eventos: %s; reconecto en %ds", e, espera)
            time.sleep(espera)
            espera = min(espera * 2, 30)
        finally:
            if db: db.close()


if __name__ == "__main__":
    main()
