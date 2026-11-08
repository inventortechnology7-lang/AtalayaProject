#!/usr/bin/env python3
"""Cliente de sincronización Katana -> Negra (contrato de Negra: docs/SINCRONIZACION.md).
Envía el outbox en orden y por lotes; solo marca enviado lo que Negra confirma.
Latido periódico. Reintentos con espera creciente. Sin NEGRA_URL no hace nada."""
import json, logging, os, sqlite3, time, urllib.request, urllib.error
from pathlib import Path

BASE = Path(__file__).resolve().parent
ENV = dict(os.environ)
if (BASE / ".env").exists():
    for l in (BASE / ".env").read_text().splitlines():
        if "=" in l and not l.startswith("#"):
            k, v = l.split("=", 1)
            ENV.setdefault(k.strip(), v.strip())
DB = ENV.get("DB_RUTA", str(BASE / "katana.db"))
URL = ENV.get("NEGRA_URL", "").rstrip("/")            # p.ej. http://100.101.225.120
USUARIO, CLAVE = ENV.get("SYNC_USUARIO", ""), ENV.get("SYNC_CLAVE", "")   # SYNC_USUARIO = correo
CONDO_ID = int(ENV.get("CONDOMINIO_ID", "1"))
CONDO = ENV.get("CONDOMINIO", "Las Palmas")
RUTA_LOGIN = ENV.get("RUTA_LOGIN", "/api/login")
RUTA_LOTE = ENV.get("RUTA_LOTE", "/api/sync/lote")
RUTA_LATIDO = ENV.get("RUTA_LATIDO", "/api/sync/latido")
RUTA_PANTALLA = ENV.get("RUTA_PANTALLA", "/api/sync/pantalla")
LOTE = int(ENV.get("SYNC_LOTE", "500"))
LATIDO_S = float(ENV.get("LATIDO_S", "30"))
log = logging.getLogger("sync")


class ErrorHttp(Exception):
    def __init__(self, code):
        super().__init__(f"HTTP {code}"); self.code = code


def iso(t, respaldo):
    """t del nodo (epoch s/ms) -> ISO UTC; si no es una hora válida usa la de recepción."""
    try:
        t = float(t)
        if t > 1e11: t /= 1000
        if t < 1.5e9: t = respaldo      # contador de arranque, no hora real
    except (TypeError, ValueError):
        t = respaldo
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t))


def armar(filas):
    """filas del outbox (en orden) -> cuerpo del lote de Negra."""
    al, lg, mu = [], [], []
    for _, _, tipo, p, creado in filas:
        d = json.loads(p)
        if tipo == "alarma":
            est = "cerrada" if not d.get("abierta", True) else ("reconocida" if d.get("reconocida") else "activa")
            al.append(dict(uid="a-" + d["uid"], sistema=d.get("sistema") or "?", severidad=int(d.get("sev") or 0),
                           detalle=d.get("detalle") or "", estado=est, creada=iso(d.get("t"), creado),
                           cerradaEn=iso(d["cerrada_en"], creado) if d.get("cerrada_en") else None))
        elif tipo == "log":
            lg.append(dict(uid="l-" + d["uid"], t=iso(d.get("t"), creado), severidad=int(d.get("sev") or 0),
                           sistema=d.get("sistema") or "?", mensaje=str(d.get("msg") or "")))
        elif tipo == "muestra":
            mu.append(dict(uid="m-" + d["uid"], sistema=d.get("sistema") or "?", magnitud=d.get("magnitud") or "?",
                           valor=d.get("valor"), unidad=d.get("unidad") or "", tomada=iso(d.get("recibido"), creado)))
    return dict(condominioId=CONDO_ID, alarmas=al, logs=lg, muestras=mu)


class Enlace:
    def __init__(self):
        self.jwt, self.jwt_t = None, 0

    def _post(self, ruta, cuerpo, auth=True):
        h = {"Content-Type": "application/json"}
        if auth:
            if not self.jwt or time.time() - self.jwt_t > 11 * 3600:   # JWT dura 12 h
                self.login()
            h["Authorization"] = "Bearer " + self.jwt
        req = urllib.request.Request(URL + ruta, json.dumps(cuerpo).encode(), h, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=15) as r:
                if r.status != 200:
                    raise ErrorHttp(r.status)
                return json.loads(r.read() or b"{}")
        except urllib.error.HTTPError as e:
            if e.code == 401:
                self.jwt = None
            raise ErrorHttp(e.code)

    def login(self):
        r = self._post(RUTA_LOGIN, {"correo": USUARIO, "clave": CLAVE}, auth=False)
        self.jwt = r.get("token")
        if not self.jwt:
            raise RuntimeError("login sin token")
        self.jwt_t = time.time()

    def enviar(self, filas):
        return self._post(RUTA_LOTE, armar(filas))

    def pantalla(self, cfg, st):
        cuerpo = {"condominioId": CONDO_ID}
        if cfg is not None: cuerpo["cfg"] = cfg
        if st is not None: cuerpo["st"] = st
        self._post(RUTA_PANTALLA, cuerpo)

    def latido(self):
        self._post(RUTA_LATIDO, {"condominioId": CONDO_ID})


def enviar_filas(enlace, db, filas):
    """Envía; 400 => aísla registro a registro y aparta (enviado=-1) el inválido para no bloquear la cola."""
    try:
        enlace.enviar(filas)
        ids = [f[0] for f in filas]
    except ErrorHttp as e:
        if e.code != 400:
            raise
        if len(filas) > 1:
            mitad = len(filas) // 2
            return enviar_filas(enlace, db, filas[:mitad]) + enviar_filas(enlace, db, filas[mitad:])
        log.error("registro %s rechazado por Negra (400), apartado: %s", filas[0][1], filas[0][3][:200])
        db.execute("UPDATE outbox SET enviado=-1 WHERE id=?", (filas[0][0],)); db.commit()
        return []
    db.executemany("UPDATE outbox SET enviado=? WHERE id=?", [(time.time(), i) for i in ids]); db.commit()
    return ids


def enviar_pantalla(enlace, db, ultima):
    """Reenvía la pantalla si su versión cambió desde `ultima`. Devuelve la versión ya enviada."""
    try:
        fila = db.execute("SELECT version, cfg, st FROM pantalla WHERE id=1").fetchone()
    except sqlite3.OperationalError:          # el receptor aún no creó la tabla
        return ultima
    if not fila or fila[0] == ultima or (fila[1] is None and fila[2] is None):
        return ultima
    enlace.pantalla(json.loads(fila[1]) if fila[1] else None, json.loads(fila[2]) if fila[2] else None)
    return fila[0]


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    if not (URL and USUARIO and CLAVE):
        log.warning("NEGRA_URL / SYNC_USUARIO / SYNC_CLAVE sin configurar: sin sincronizar (los datos se acumulan).")
        while not (URL and USUARIO and CLAVE):
            time.sleep(3600)
    enlace, espera, ult_latido = Enlace(), 2, 0
    ver_pantalla = None                            # None => reenviar al arrancar y al reconectar
    while True:
        db = None
        try:
            db = sqlite3.connect(DB, timeout=10)
            v = enviar_pantalla(enlace, db, ver_pantalla)
            if v != ver_pantalla:
                ver_pantalla = v
                ult_latido = time.time()           # la pantalla también cuenta como latido
            if time.time() - ult_latido >= LATIDO_S:
                enlace.latido()
                ult_latido = time.time()
            filas = db.execute("SELECT id,uid,tipo,payload,creado FROM outbox WHERE enviado IS NULL ORDER BY id LIMIT ?",
                               (LOTE,)).fetchall()
            if filas:
                n = len(enviar_filas(enlace, db, filas))
                ult_latido = time.time()           # el lote también cuenta como latido
                log.info("enviados %d/%d", n, len(filas))
                espera = 2
                continue                           # más lotes sin esperar
            espera = 2
            time.sleep(1)                          # pantalla: máx. ~1 envío por segundo
        except Exception as e:
            ver_pantalla = None                    # al volver el enlace, reenviar la pantalla
            log.warning("sin enlace con Negra (%s); reintento en %ds", e, espera)
            time.sleep(espera)
            espera = min(espera * 2, 60)
        finally:
            if db: db.close()


if __name__ == "__main__":
    main()
