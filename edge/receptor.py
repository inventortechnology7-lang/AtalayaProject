#!/usr/bin/env python3
"""Receptor TCP de nodos (protocolo Atalaya) para Katana. Guarda todo en SQLite local + outbox."""
import functools
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
# Solo la pantalla (Minima por el puente USB local) se reenvía a Negra como pantalla; los nodos no.
# Elementos de la pantalla por puerta: Sensor 1, Sensor 2, Motor (orden #006)
EL_INDICES = {"A": (30, 31, 32), "B": (33, 34, 35)}
SIN_DATOS_S = float(ENV.get("PUERTA_SIN_DATOS_S", "120"))
PANTALLA_ORIGEN = {x.strip() for x in ENV.get("PANTALLA_ORIGEN", "127.0.0.1,::1").split(",") if x.strip()}
ORDENES_SOCK = ENV.get("ORDENES_SOCK", str(BASE / "ordenes.sock"))   # ordenes.py -> receptor (orden #009)
LINEAS_PERMITIDAS = {"REINICIO", "ORDEN"}
ORIGEN_TXT = {"app": "aplicativo", "web": "web"}
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
CREATE TABLE IF NOT EXISTS puertas(pue TEXT PRIMARY KEY, nodo TEXT, puerta TEXT, el TEXT, up INTEGER,
  actualizado REAL, caida INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS pantalla(id INTEGER PRIMARY KEY CHECK(id=1), nodo TEXT, cfg TEXT, st TEXT,
  version INTEGER DEFAULT 0, cambiado REAL);
"""


def uid_de(*partes):
    return hashlib.sha256("|".join(str(p) for p in partes).encode()).hexdigest()[:32]


def atomic(method):
    """Persist state and outbox together, including when called in a larger transaction."""
    @functools.wraps(method)
    def wrapped(self, *args, **kwargs):
        self.db.execute("SAVEPOINT mutation")
        try:
            result = method(self, *args, **kwargs)
            self.db.execute("RELEASE mutation")
            return result
        except BaseException:
            self.db.execute("ROLLBACK TO mutation")
            self.db.execute("RELEASE mutation")
            raise
    return wrapped


class Almacen:
    def __init__(self, ruta):
        self.db = sqlite3.connect(ruta, isolation_level=None)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=FULL")
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

    @atomic
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

    @atomic
    def log(self, nodo, t, sev, sis, msg):
        uid = uid_de("lg", nodo, t, sev, sis, msg)
        if self.db.execute("INSERT OR IGNORE INTO logs VALUES(?,?,?,?,?,?)", (uid, nodo, t, sev, sis, msg)).rowcount:
            self._outbox(uid, "log", dict(uid=uid, nodo=nodo, t=t, sev=sev, sistema=sis, msg=msg))

    def pantalla(self, nodo, cfg=None, st=None):
        """Guarda el último cfg/st de la placa; sube version solo si algo cambió (sync.py lo reenvía a Negra)."""
        fila = self.db.execute("SELECT cfg, st FROM pantalla WHERE id=1").fetchone() or (None, None)
        nuevo_cfg = json.dumps(cfg, ensure_ascii=False, sort_keys=True) if cfg is not None else fila[0]
        nuevo_st = json.dumps(st, ensure_ascii=False, sort_keys=True) if st is not None else fila[1]
        if (nuevo_cfg, nuevo_st) == tuple(fila):
            return False
        self.db.execute("""INSERT INTO pantalla(id,nodo,cfg,st,version,cambiado) VALUES(1,?,?,?,1,?)
          ON CONFLICT(id) DO UPDATE SET nodo=excluded.nodo, cfg=excluded.cfg, st=excluded.st,
          version=pantalla.version+1, cambiado=excluded.cambiado""", (nodo, nuevo_cfg, nuevo_st, time.time()))
        return True

    def puerta(self, nodo, st):
        """Guarda el estado de la puerta (st.pue). Devuelve (pue, el_lista) si 'el' cambió o volvió de caída."""
        pue = str(st.get("pue") or "").upper()
        if not pue:
            return None
        el = st.get("el") if isinstance(st.get("el"), list) else None
        fila = self.db.execute("SELECT el, caida FROM puertas WHERE pue=?", (pue,)).fetchone()
        el_txt = json.dumps(el) if el is not None else (fila[0] if fila else None)
        self.db.execute("""INSERT INTO puertas(pue,nodo,puerta,el,up,actualizado,caida) VALUES(?,?,?,?,?,?,0)
          ON CONFLICT(pue) DO UPDATE SET nodo=excluded.nodo, puerta=COALESCE(excluded.puerta,puertas.puerta),
          el=excluded.el, up=COALESCE(excluded.up,puertas.up), actualizado=excluded.actualizado, caida=0""",
                        (pue, nodo, st.get("puerta"), el_txt, st.get("up"), time.time()))
        if el is not None and (fila is None or fila[1] or fila[0] != el_txt):
            return pue, el
        return None

    def tocar_puertas(self, nodo):
        self.db.execute("UPDATE puertas SET actualizado=? WHERE nodo=? AND caida=0", (time.time(), nodo))

    @atomic
    def puertas_caidas(self, ahora=None):
        """Marca caídas las puertas sin datos en SIN_DATOS_S, abre su alarma sev 2. Devuelve las nuevas caídas."""
        ahora = ahora or time.time()
        nuevas = []
        for pue, nodo, act in self.db.execute(
                "SELECT pue,nodo,actualizado FROM puertas WHERE caida=0 AND actualizado<?", (ahora - SIN_DATOS_S,)).fetchall():
            self.db.execute("UPDATE puertas SET caida=1 WHERE pue=?", (pue,))
            det = f"Puerta {pue} sin comunicacion"
            uid = uid_de("al", nodo, "Puertas", round(act), det)
            self.db.execute("INSERT OR IGNORE INTO alarmas(uid,nodo,sistema,sev,reconocida,t,detalle) VALUES(?,?,?,?,?,?,?)",
                            (uid, nodo, "Puertas", 2, 0, ahora, det))
            self._outbox(uid + ":a", "alarma", dict(uid=uid, nodo=nodo, sistema="Puertas", sev=2, reconocida=False,
                                                    t=ahora, detalle=det, abierta=True))
            self.log(nodo, ahora, 2, "Puertas", det)
            nuevas.append(pue)
        return nuevas

    def els_actuales(self):
        """[(indice, valor)] de todas las puertas conocidas (caída => 1 en sus 3 elementos)."""
        res = []
        for pue, el, caida in self.db.execute("SELECT pue, el, caida FROM puertas ORDER BY pue"):
            idx = EL_INDICES.get(pue)
            if not idx:
                continue
            vals = [1, 1, 1] if caida else (json.loads(el) if el else [])
            res += [(i, 1 if v else 0) for i, v in zip(idx, vals)]
        return res

    def nodo_de_puerta(self, pue):
        fila = self.db.execute("SELECT nodo, caida FROM puertas WHERE pue=?", (pue,)).fetchone()
        return fila if fila else (None, 1)

    @atomic
    def muestra(self, nodo, sis, mag, val, uni):
        ahora = time.time()
        uid = uid_de("mu", nodo, sis, mag, val, round(ahora, 3))
        self.db.execute("INSERT OR IGNORE INTO muestras VALUES(?,?,?,?,?,?,?)", (uid, nodo, ahora, sis, mag, val, uni))
        self._outbox(uid, "muestra", dict(uid=uid, nodo=nodo, recibido=ahora, sistema=sis,
                                          magnitud=mag, valor=val, unidad=uni))


ALM: Almacen = None
PANTALLAS = set()   # writers de conexiones de la pantalla (origen PANTALLA_ORIGEN)
ESCRITORES = {}     # nodo (IP) -> writer de su conexión TCP activa


async def entregar_orden(pue, linea, origen, oid=""):
    """Manda `linea` a la placa de la puerta `pue`. Guarda el log (va a Negra en el lote). Devuelve (ok, texto)."""
    nodo, caida = ALM.nodo_de_puerta(pue)
    w = ESCRITORES.get(nodo) if nodo else None
    base = f"Orden remota {linea} ({ORIGEN_TXT.get(origen, origen or '?')})" + (f" #{oid}" if oid else "")
    ok = False
    if w is not None and not w.is_closing():
        try:
            w.write((linea + "\n").encode()); await asyncio.wait_for(w.drain(), 5)
            ok = True
        except Exception as e:
            log.warning("orden a Puerta %s falló: %s", pue, e)
    txt = f"{base} entregada a Puerta {pue}" if ok else f"{base} no entregada a Puerta {pue}: puerta sin conexión"
    ALM.log(nodo or "katana", time.time(), 0 if ok else 2, "Puertas", txt)
    (log.info if ok else log.warning)(txt)
    return ok, txt


async def atender_control(reader, writer):
    """Socket local (solo ordenes.py): 'ORDEN <A|B> <REINICIO|ORDEN> <app|web>' -> 'OK ...' / 'NO ...'."""
    try:
        linea = (await asyncio.wait_for(reader.readline(), 5)).decode("utf-8", "replace").split()
        if len(linea) in (4, 5) and linea[0] == "ORDEN" and linea[1] in EL_INDICES and linea[2] in LINEAS_PERMITIDAS:
            ok, txt = await entregar_orden(linea[1], linea[2], linea[3], linea[4] if len(linea) == 5 and linea[4].isdigit() else "")
            writer.write(f"{'OK' if ok else 'NO'} {txt}\n".encode())
        else:
            writer.write(b"NO orden invalida\n")
        await writer.drain()
    except Exception as e:
        log.warning("control: %s", e)
    finally:
        writer.close()


def lineas_el(pue, el):
    idx = EL_INDICES.get(pue)
    return [f"EL {i} {1 if v else 0}" for i, v in zip(idx, el)] if idx else []


def a_pantallas(lineas):
    for w in list(PANTALLAS):
        try:
            for l in lineas:
                w.write((l + "\n").encode())
        except Exception:
            PANTALLAS.discard(w)


async def vigilar_puertas():
    while True:
        await asyncio.sleep(10)
        try:
            for pue in ALM.puertas_caidas():
                log.warning("Puerta %s sin comunicación", pue)
                a_pantallas(lineas_el(pue, [1, 1, 1]))
        except Exception as e:
            log.warning("vigilar_puertas: %s", e)


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
        ESCRITORES[nodo] = writer
        if nodo in PANTALLA_ORIGEN:
            PANTALLAS.add(writer)
            a_pantallas([f"EL {i} {v}" for i, v in ALM.els_actuales()])

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
                ALM.tocar_puertas(nodo)
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
        PANTALLAS.discard(writer)
        if ESCRITORES.get(nodo) is writer:
            del ESCRITORES[nodo]
            ALM.desconectado(nodo)
        log.info("%s desconectado", addr)
        writer.close()


def procesar(nodo, addr, sistemas, msg):
    if "cfg" in msg:
        cor = msg["cfg"].get("cor", [])
        if cor:
            sistemas = [str(c) for c in cor]
            ALM.nodo_conectado(nodo, addr, sistemas)
    if nodo in PANTALLA_ORIGEN and (isinstance(msg.get("cfg"), dict) or isinstance(msg.get("st"), dict)):
        ALM.pantalla(nodo, msg["cfg"] if isinstance(msg.get("cfg"), dict) else None,
                     msg["st"] if isinstance(msg.get("st"), dict) else None)
    if isinstance(msg.get("st"), dict) and msg["st"].get("pue"):
        cambio = ALM.puerta(nodo, msg["st"])
        if cambio:
            a_pantallas(lineas_el(*cambio))
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
    asyncio.create_task(vigilar_puertas())
    try:
        os.unlink(ORDENES_SOCK)
    except FileNotFoundError:
        pass
    ctl = await asyncio.start_unix_server(atender_control, ORDENES_SOCK)
    os.chmod(ORDENES_SOCK, 0o600)
    log.info("Órdenes remotas: socket local %s", ORDENES_SOCK)
    async with srv:
        await srv.serve_forever()


if __name__ == "__main__":
    asyncio.run(main())
