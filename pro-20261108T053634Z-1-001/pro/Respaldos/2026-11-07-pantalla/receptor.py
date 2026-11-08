#!/usr/bin/env python3
"""Receptor TCP de nodos (protocolo Atalaya) para Katana. Guarda todo en SQLite local + outbox."""
import asyncio, hashlib, hmac, json, logging, os, sqlite3, time
from pathlib import Path

BASE = Path(__file__).resolve().parent
MAX_LINEA = 64 * 1024


def cargar_env():
    env = dict(os.environ)
    f = BASE / ".env"
    if f.exists():
        for l in f.read_text().splitlines():
            if "=" in l and not l.startswith("#"):
                k, v = l.split("=", 1)
                env.setdefault(k.strip(), v.strip())
    return env


ENV = cargar_env()
TOKEN = ENV.get("PLACA_TOKEN", "")
PUERTO = int(ENV.get("PUERTO", "8300"))
DB_RUTA = ENV.get("DB_RUTA", str(BASE / "katana.db"))
CONDOMINIO = ENV.get("CONDOMINIO", "Las Palmas")
log = logging.getLogger("receptor")

SCHEMA = """
CREATE TABLE IF NOT EXISTS nodos(nodo TEXT PRIMARY KEY, direccion TEXT, sistemas TEXT,
  primera_conexion REAL, ultimo_contacto REAL, conectado INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS alarmas(uid TEXT PRIMARY KEY, nodo TEXT, sistema TEXT, sev INTEGER,
  reconocida INTEGER, t REAL, detalle TEXT, abierta INTEGER DEFAULT 1, cerrada_en REAL);
CREATE TABLE IF NOT EXISTS logs(uid TEXT PRIMARY KEY, nodo TEXT, t REAL, sev INTEGER, sistema TEXT, msg TEXT);
CREATE TABLE IF NOT EXISTS muestras(uid TEXT PRIMARY KEY, nodo TEXT, recibido REAL, sistema TEXT,
  magnitud TEXT, valor REAL, unidad TEXT);
CREATE TABLE IF NOT EXISTS outbox(id INTEGER PRIMARY KEY AUTOINCREMENT, uid TEXT UNIQUE, tipo TEXT,
  payload TEXT, creado REAL, enviado REAL);
CREATE INDEX IF NOT EXISTS ix_outbox_pend ON outbox(enviado);
"""


def uid_de(*partes):
    return hashlib.sha256("|".join(str(p) for p in partes).encode()).hexdigest()[:32]


class Almacen:
    def __init__(self, ruta):
        self.db = sqlite3.connect(ruta, isolation_level=None)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=NORMAL")
        self.db.executescript(SCHEMA)
        self.db.execute("UPDATE nodos SET conectado=0")

    def _outbox(self, uid, tipo, payload):
        self.db.execute("INSERT OR IGNORE INTO outbox(uid,tipo,payload,creado) VALUES(?,?,?,?)",
                        (uid, tipo, json.dumps(payload, ensure_ascii=False), time.time()))

    def nodo_conectado(self, nodo, addr, sistemas=None):
        ahora = time.time()
        self.db.execute("""INSERT INTO nodos(nodo,direccion,sistemas,primera_conexion,ultimo_contacto,conectado)
          VALUES(?,?,?,?,?,1) ON CONFLICT(nodo) DO UPDATE SET direccion=excluded.direccion,
          ultimo_contacto=excluded.ultimo_contacto, conectado=1,
          sistemas=COALESCE(excluded.sistemas,nodos.sistemas)""",
                        (nodo, addr, json.dumps(sistemas) if sistemas else None, ahora, ahora))

    def tocar(self, nodo):
        self.db.execute("UPDATE nodos SET ultimo_contacto=? WHERE nodo=?", (time.time(), nodo))

    def desconectado(self, nodo):
        self.db.execute("UPDATE nodos SET conectado=0 WHERE nodo=?", (nodo,))

    def alarmas_activas(self, nodo, sistemas, lista):
        """lista = alarmas activas ahora; lo que no aparece se cierra."""
        ahora = time.time()
        vistas = set()
        for a in lista:
            idx, sev, ack, t, det = (list(a) + [None] * 5)[:5]
            sis = sistemas[idx] if isinstance(idx, int) and 0 <= idx < len(sistemas) else f"sistema{idx}"
            uid = uid_de("al", nodo, sis, t, det)
            vistas.add(uid)
            cur = self.db.execute("SELECT abierta, reconocida FROM alarmas WHERE uid=?", (uid,)).fetchone()
            if cur is None:
                self.db.execute("INSERT INTO alarmas(uid,nodo,sistema,sev,reconocida,t,detalle) VALUES(?,?,?,?,?,?,?)",
                                (uid, nodo, sis, sev, int(bool(ack)), t, det))
                self._outbox(uid + ":a", "alarma", dict(uid=uid, nodo=nodo, sistema=sis, sev=sev,
                             reconocida=bool(ack), t=t, detalle=det, abierta=True))
            elif cur[1] != int(bool(ack)):
                self.db.execute("UPDATE alarmas SET reconocida=? WHERE uid=?", (int(bool(ack)), uid))
                self._outbox(uid + f":ack{int(bool(ack))}", "alarma", dict(uid=uid, nodo=nodo, sistema=sis,
                             sev=sev, reconocida=bool(ack), t=t, detalle=det, abierta=True))
        for uid, sis, sev, t, det in self.db.execute(
                "SELECT uid,sistema,sev,t,detalle FROM alarmas WHERE nodo=? AND abierta=1", (nodo,)).fetchall():
            if uid not in vistas:
                self.db.execute("UPDATE alarmas SET abierta=0, cerrada_en=? WHERE uid=?", (ahora, uid))
                self._outbox(uid + ":c", "alarma", dict(uid=uid, nodo=nodo, sistema=sis, sev=sev, t=t,
                             detalle=det, abierta=False, cerrada_en=ahora))

    def log(self, nodo, t, sev, sis, msg):
        uid = uid_de("lg", nodo, t, sev, sis, msg)
        if self.db.execute("INSERT OR IGNORE INTO logs VALUES(?,?,?,?,?,?)", (uid, nodo, t, sev, sis, msg)).rowcount:
            self._outbox(uid, "log", dict(uid=uid, nodo=nodo, t=t, sev=sev, sistema=sis, msg=msg))

    def muestra(self, nodo, sis, mag, val, uni):
        ahora = time.time()
        uid = uid_de("mu", nodo, sis, mag, val, round(ahora, 3))
        self.db.execute("INSERT OR IGNORE INTO muestras VALUES(?,?,?,?,?,?,?)", (uid, nodo, ahora, sis, mag, val, uni))
        self._outbox(uid, "muestra", dict(uid=uid, nodo=nodo, recibido=ahora, sistema=sis,
                                          magnitud=mag, valor=val, unidad=uni))


ALM: Almacen = None


async def atender(reader, writer):
    peer = writer.get_extra_info("peername")
    addr = f"{peer[0]}:{peer[1]}" if peer else "?"
    nodo = peer[0] if peer else "?"
    sistemas = []
    try:
        try:
            primera = await asyncio.wait_for(reader.readline(), 10)
        except (asyncio.TimeoutError, ValueError, asyncio.LimitOverrunError):
            log.warning("%s sin TOKEN a tiempo / línea inválida", addr); return
        txt = primera.decode("utf-8", "replace").strip()
        if not (txt.startswith("TOKEN ") and TOKEN and hmac.compare_digest(txt[6:].strip(), TOKEN)):
            log.warning("%s token incorrecto, conexión cerrada", addr); return
        log.info("%s conectado", addr)
        ALM.nodo_conectado(nodo, addr)
        writer.write(f"HORA {int(time.time())}\n".encode()); await writer.drain()

        async def latido():
            while True:
                await asyncio.sleep(15)
                writer.write(b"SYNC\n"); await writer.drain()
        tarea = asyncio.create_task(latido())
        try:
            while True:
                try:
                    linea = await asyncio.wait_for(reader.readline(), 120)
                except asyncio.TimeoutError:
                    log.warning("%s sin datos 120 s, cerrando", addr); break
                except (ValueError, asyncio.LimitOverrunError):
                    log.warning("%s línea > 64 KB, cerrando", addr); break
                if not linea:
                    break
                ALM.tocar(nodo)
                try:
                    msg = json.loads(linea.decode("utf-8", "replace"))
                    if not isinstance(msg, dict):
                        raise ValueError("no es objeto")
                    sistemas = procesar(nodo, addr, sistemas, msg)
                except Exception as e:
                    log.warning("%s mensaje mal formado ignorado: %s", addr, e)
        finally:
            tarea.cancel()
    except (ConnectionError, OSError):
        pass
    finally:
        ALM.desconectado(nodo)
        log.info("%s desconectado", addr)
        writer.close()


def procesar(nodo, addr, sistemas, msg):
    if "cfg" in msg:
        cor = msg["cfg"].get("cor", [])
        if cor:
            sistemas = [str(c) for c in cor]
            ALM.nodo_conectado(nodo, addr, sistemas)
    if "st" in msg:
        ALM.alarmas_activas(nodo, sistemas, msg["st"].get("al", []))
    if "logs" in msg:
        for r in msg["logs"]:
            t, sev, sis, m = (list(r) + [None] * 4)[:4]
            ALM.log(nodo, t, sev, sis, m)
    if "log" in msg:
        r = msg["log"]
        ALM.log(nodo, r.get("t"), r.get("v"), r.get("s"), r.get("m"))
    if "m" in msg:
        for r in msg["m"]:
            sis, mag, val, uni = (list(r) + [None] * 4)[:4]
            ALM.muestra(nodo, sis, mag, val, uni)
    return sistemas


async def main():
    global ALM
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    if not TOKEN:
        raise SystemExit("Falta PLACA_TOKEN en .env")
    ALM = Almacen(DB_RUTA)
    srv = await asyncio.start_server(atender, "0.0.0.0", PUERTO, limit=MAX_LINEA)
    log.info("Receptor de %s escuchando en :%d", CONDOMINIO, PUERTO)
    async with srv:
        await srv.serve_forever()


if __name__ == "__main__":
    asyncio.run(main())
