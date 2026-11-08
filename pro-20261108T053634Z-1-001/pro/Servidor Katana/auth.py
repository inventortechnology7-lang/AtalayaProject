"""Usuarios y accesos locales de Katana (funciona sin internet). Claves con scrypt + sal; nunca en texto plano."""
import hashlib, hmac, os, sqlite3, time
from pathlib import Path

DB = str(Path(__file__).resolve().parent / "usuarios.db")
ROLES = ["admin", "tecnico", "operador"]
MAX_FALLOS, VENTANA_S = 5, 300


def _conn():
    c = sqlite3.connect(DB, timeout=10)
    c.executescript("""CREATE TABLE IF NOT EXISTS usuarios(correo TEXT PRIMARY KEY, nombre TEXT, rol TEXT,
        sal BLOB, clave BLOB, activo INTEGER DEFAULT 1, creado REAL);
        CREATE TABLE IF NOT EXISTS accesos(id INTEGER PRIMARY KEY AUTOINCREMENT, t REAL, correo TEXT, evento TEXT, detalle TEXT);""")
    try:
        os.chmod(DB, 0o600)
    except OSError:
        pass
    return c


def _hash(clave, sal):
    return hashlib.scrypt(clave.encode(), salt=sal, n=2 ** 14, r=8, p=1, dklen=32)


def registrar(correo, evento, detalle=""):
    c = _conn(); c.execute("INSERT INTO accesos(t,correo,evento,detalle) VALUES(?,?,?,?)", (time.time(), correo, evento, detalle)); c.commit(); c.close()


def hay_usuarios():
    c = _conn(); n = c.execute("SELECT COUNT(*) FROM usuarios").fetchone()[0]; c.close(); return n > 0


def crear(correo, nombre, rol, clave, por=None):
    correo = correo.strip().lower()
    if "@" not in correo or "." not in correo.split("@")[-1]:
        return False, "Correo no válido."
    if not nombre.strip():
        return False, "Falta el nombre."
    if rol not in ROLES:
        return False, "Rol no válido."
    if len(clave) < 8:
        return False, "La clave debe tener al menos 8 caracteres."
    c = _conn()
    try:
        sal = os.urandom(16)
        c.execute("INSERT INTO usuarios(correo,nombre,rol,sal,clave,creado) VALUES(?,?,?,?,?,?)",
                  (correo, nombre.strip(), rol, sal, _hash(clave, sal), time.time())); c.commit()
    except sqlite3.IntegrityError:
        return False, "Ese correo ya existe."
    finally:
        c.close()
    registrar(correo, "usuario_creado", f"rol={rol} por={por or 'inicial'}")
    return True, "Usuario creado."


def verificar(correo, clave):
    """-> (True, {correo,nombre,rol}) o (False, mensaje)."""
    correo = correo.strip().lower()
    c = _conn()
    fallos = c.execute("SELECT COUNT(*) FROM accesos WHERE correo=? AND evento='login_fallo' AND t>?",
                       (correo, time.time() - VENTANA_S)).fetchone()[0]
    if fallos >= MAX_FALLOS:
        c.close(); return False, "Demasiados intentos fallidos. Espera 5 minutos."
    u = c.execute("SELECT correo,nombre,rol,sal,clave,activo FROM usuarios WHERE correo=?", (correo,)).fetchone()
    c.close()
    sal = u[3] if u else b"\0" * 16
    ok = hmac.compare_digest(_hash(clave, sal), u[4] if u else b"\0" * 32) and u is not None and u[5] == 1
    if ok:
        registrar(correo, "login_ok"); return True, dict(correo=u[0], nombre=u[1], rol=u[2])
    registrar(correo, "login_fallo", "usuario inexistente" if not u else ("desactivado" if u[5] != 1 else "clave incorrecta"))
    return False, "Correo o clave incorrectos."


def listar():
    c = _conn(); r = c.execute("SELECT correo,nombre,rol,activo,creado FROM usuarios ORDER BY creado").fetchall(); c.close(); return r


def activar(correo, activo, por):
    c = _conn(); c.execute("UPDATE usuarios SET activo=? WHERE correo=?", (int(activo), correo)); c.commit(); c.close()
    registrar(correo, "usuario_activado" if activo else "usuario_desactivado", f"por={por}")


def accesos(n=40):
    c = _conn(); r = c.execute("SELECT t,correo,evento,detalle FROM accesos ORDER BY id DESC LIMIT ?", (n,)).fetchall(); c.close(); return r
