#!/usr/bin/env python3
"""Atalaya · Katana — programa de escritorio local (GTK4) con acceso por correo y clave.
Lee la base local (solo lectura); funciona sin internet."""
import json, sys, time
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, GLib, Gdk
import ui, auth   # ui.estado(): consulta de solo lectura a katana.db

CSS = b"""
window,.fondo{background:#0d0b1f;color:#eeeeee;}
.card{background:#1b1832;border:1px solid #2c2850;border-radius:12px;padding:12px 14px;}
.login{background:#1b1832;border:1px solid #2c2850;border-radius:16px;padding:28px 32px;}
.banner{border-radius:14px;padding:16px 20px;border:1px solid;}
.big{font-size:22px;font-weight:700;} .mu{color:#9a96b8;font-size:12px;}
.titulo{font-size:12px;font-weight:700;color:#9a96b8;letter-spacing:1px;margin-top:10px;}
.ok{color:#4cd387;}.wa{color:#f0b43c;}.er{color:#ff6b78;}.off{color:#7c7898;}
.pill{border:1px solid;border-radius:99px;padding:0 9px;font-size:12px;}
.sis{font-size:16px;font-weight:700;}
.proyecto{font-size:24px;font-weight:800;color:#ffffff;}
.modo{border:1px solid #aa3bff;color:#aa3bff;border-radius:99px;padding:2px 10px;font-size:12px;}
.error{color:#ff6b78;font-size:13px;}
notebook>header{background:#0d0b1f;}
notebook>header>tabs>tab{color:#9a96b8;padding:8px 16px;}
notebook>header>tabs>tab:checked{color:#aa3bff;border-bottom:2px solid #aa3bff;}
scrolledwindow,viewport{background:transparent;}
button.suggested-action{background:#8a3ff2;color:#ffffff;}
list,row{background:transparent;}
row:selected{background:#2c2850;}
"""
SOLO_CORREO = False   # correo + clave por usuario; True = solo correo (sin clave)
SEV_T = ["info", "aviso", "falla", "crítica"]
SEV_C = ["ok", "wa", "er", "er"]


def fecha(t):
    if not t:
        return "—"
    t = float(t) / 1000 if float(t) > 1e11 else float(t)
    return time.strftime("%d/%m/%Y %H:%M:%S", time.localtime(t))


def hace(s):
    return f"{s:.0f} s" if s < 60 else f"{s/60:.0f} min" if s < 3600 else f"{s/3600:.0f} h"


def nombres(n):
    try:
        return json.loads(n["sistemas"]) or []
    except Exception:
        return []


def lbl(txt, *clases, xalign=0.0, wrap=False):
    l = Gtk.Label(label=str(txt), xalign=xalign, wrap=wrap)
    for c in clases:
        l.add_css_class(c)
    return l


def limpiar(box):
    h = box.get_first_child()
    while h:
        n = h.get_next_sibling()
        box.remove(h)
        h = n


def pill(cls, txt):
    p = lbl(txt, "pill", cls); p.set_valign(Gtk.Align.CENTER); return p


def sev(x):
    return min(max(int(x or 0), 0), 3)


def logo_widget(ancho=64, alto=41):
    p = Gtk.Picture.new_for_filename(str(AQUI / "assets" / "logo.png"))
    p.set_size_request(ancho, alto); p.set_can_shrink(True); p.set_content_fit(Gtk.ContentFit.CONTAIN)
    return p


class Ventana(Gtk.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title="Atalaya · Condominio Las Palmas")
        self.set_default_size(1050, 740)
        self.usuario, self.tid, self.sel_sis, self._recon = None, None, None, False
        self.pila = Gtk.Stack(); self.set_child(self.pila)
        self.pila.add_named(self.pantalla_login(), "login")
        self.pila.add_named(self.pantalla_primero(), "primero")
        self.pila.add_named(self.pantalla_app(), "app")
        self.connect("close-request", self.al_cerrar)
        self.mostrar_acceso()

    # ---------- acceso ----------
    def tarjeta_acceso(self, titulo, sub):
        ext = Gtk.Box(halign=Gtk.Align.CENTER, valign=Gtk.Align.CENTER)
        c = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10); c.add_css_class("login"); c.set_size_request(360, -1)
        lg = logo_widget(120, 77); lg.set_halign(Gtk.Align.CENTER); c.append(lg)
        c.append(lbl("Atalaya", "proyecto", xalign=0.5)); c.append(lbl(sub, "mu", xalign=0.5))
        ext.append(c); return ext, c

    def pantalla_login(self):
        ext, c = self.tarjeta_acceso("Atalaya", "Inventor Technology · Condominio Las Palmas")
        self.l_correo = Gtk.Entry(placeholder_text="Correo", input_purpose=Gtk.InputPurpose.EMAIL)
        self.l_clave = Gtk.PasswordEntry(placeholder_text="Clave", show_peek_icon=True)
        self.l_error = lbl("", "error", xalign=0.5, wrap=True)
        b = Gtk.Button(label="Entrar"); b.add_css_class("suggested-action"); b.connect("clicked", self.entrar)
        self.l_correo.connect("activate", lambda *_: self.l_clave.grab_focus())
        self.l_clave.connect("activate", self.entrar)
        self.l_clave.set_visible(not SOLO_CORREO)
        if SOLO_CORREO: self.l_correo.connect("activate", self.entrar)
        for w in (self.l_correo, self.l_clave, self.l_error, b): c.append(w)
        return ext

    def pantalla_primero(self):
        ext, c = self.tarjeta_acceso("Atalaya", "Primer uso: crea el administrador")
        self.p_correo = Gtk.Entry(placeholder_text="Correo del administrador")
        self.p_nombre = Gtk.Entry(placeholder_text="Nombre")
        self.p_clave = Gtk.PasswordEntry(placeholder_text="Clave (mínimo 8 caracteres)", show_peek_icon=True)
        self.p_clave2 = Gtk.PasswordEntry(placeholder_text="Repite la clave")
        self.p_error = lbl("", "error", xalign=0.5, wrap=True)
        b = Gtk.Button(label="Crear administrador"); b.add_css_class("suggested-action"); b.connect("clicked", self.crear_primero)
        for w in (self.p_correo, self.p_nombre, self.p_clave, self.p_clave2, self.p_error, b): c.append(w)
        return ext

    def mostrar_acceso(self):
        self.pila.set_visible_child_name("login" if (SOLO_CORREO or auth.hay_usuarios()) else "primero")

    def crear_primero(self, *_):
        if self.p_clave.get_text() != self.p_clave2.get_text():
            self.p_error.set_label("Las claves no coinciden."); return
        ok, msg = auth.crear(self.p_correo.get_text(), self.p_nombre.get_text(), "admin", self.p_clave.get_text())
        if not ok:
            self.p_error.set_label(msg); return
        self.p_clave.set_text(""); self.p_clave2.set_text(""); self.p_error.set_label("")
        self.mostrar_acceso()

    def entrar(self, *_):
        if SOLO_CORREO:
            c = self.l_correo.get_text().strip().lower()
            if "@" not in c or "." not in c.split("@")[-1] or " " in c:
                self.l_error.set_label("Escribe un correo válido."); return
            auth.registrar(c, "login_ok", "solo correo")
            ok, r = True, dict(correo=c, nombre=c, rol="operador")
        else:
            ok, r = auth.verificar(self.l_correo.get_text(), self.l_clave.get_text())
        self.l_clave.set_text("")
        if not ok:
            self.l_error.set_label(r); return
        self.l_error.set_label(""); self.l_correo.set_text("")
        self.usuario = r
        self.quien.set_label(r["correo"] if SOLO_CORREO else f"{r['nombre']} · {r['rol']}")
        self.pag_usuarios.set_visible(r["rol"] == "admin" and not SOLO_CORREO)
        if not SOLO_CORREO: self.refrescar_usuarios()
        self.pila.set_visible_child_name("app")
        self.tick()
        self.tid = GLib.timeout_add_seconds(3, self.tick)

    def salir(self, *_):
        if self.usuario:
            auth.registrar(self.usuario["correo"], "logout")
        self.usuario = None
        if self.tid:
            GLib.source_remove(self.tid); self.tid = None
        self.mostrar_acceso()

    def al_cerrar(self, *_):
        if self.usuario:
            auth.registrar(self.usuario["correo"], "logout", "cierre de ventana")
        return False

    # ---------- aplicación ----------
    def pantalla_app(self):
        raiz = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        cab = Gtk.Box(spacing=12, margin_top=12, margin_bottom=10, margin_start=16, margin_end=16)
        tit = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        tit.append(lbl("Atalaya", "proyecto"))
        self.sub = lbl("Inventor Technology · Condominio · Proyecto Atalaya", "mu"); tit.append(self.sub)
        cab.append(logo_widget()); cab.append(tit); cab.append(Gtk.Box(hexpand=True))
        self.quien = lbl("", "mu"); cab.append(self.quien)
        sb = Gtk.Button(label="Cerrar sesión"); sb.connect("clicked", self.salir); cab.append(sb)
        cab.append(lbl("Servidor local Katana", "modo"))
        raiz.append(cab)
        self.banner = Gtk.Box(spacing=14, margin_start=16, margin_end=16, margin_bottom=6); self.banner.add_css_class("banner")
        self.bt = lbl("Cargando…", "big"); self.bs = lbl("", "mu")
        bv = Gtk.Box(orientation=Gtk.Orientation.VERTICAL); bv.append(self.bt); bv.append(self.bs)
        self.banner.append(bv); raiz.append(self.banner)
        self.nb = Gtk.Notebook(vexpand=True, margin_start=10, margin_end=10, margin_bottom=10); raiz.append(self.nb)
        self.cajas = {}
        for clave, titulo in [("res", "Resumen"), ("al", "Alarmas"), ("lg", "Registros"), ("nd", "Nodos")]:
            caja = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8, margin_top=12, margin_start=6, margin_end=6, margin_bottom=12)
            sc = Gtk.ScrolledWindow(); sc.set_child(caja); self.nb.append_page(sc, Gtk.Label(label=titulo)); self.cajas[clave] = caja
        # pestaña Sistemas: lista a la izquierda (crece con los sistemas) y detalle a la derecha
        pan = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL, position=240, margin_top=12)
        self.lista = Gtk.ListBox(selection_mode=Gtk.SelectionMode.SINGLE); self.lista.connect("row-selected", self.al_elegir)
        s1 = Gtk.ScrolledWindow(); s1.set_child(self.lista); s1.set_size_request(200, -1); pan.set_start_child(s1)
        self.detalle = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8, margin_start=14, margin_end=6, margin_bottom=12)
        s2 = Gtk.ScrolledWindow(); s2.set_child(self.detalle); pan.set_end_child(s2)
        self.nb.insert_page(pan, Gtk.Label(label="Sistemas"), 1)
        # pestaña Usuarios (solo admin)
        self.pag_usuarios_caja = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8, margin_top=12, margin_start=6, margin_end=6, margin_bottom=12)
        sc = Gtk.ScrolledWindow(); sc.set_child(self.pag_usuarios_caja)
        self.nb.append_page(sc, Gtk.Label(label="Usuarios")); self.pag_usuarios = self.nb.get_nth_page(self.nb.get_n_pages() - 1)
        self.u_form()
        return raiz

    def u_form(self):
        B = self.pag_usuarios_caja
        B.append(lbl("NUEVO USUARIO", "titulo"))
        f = Gtk.Box(spacing=8)
        self.u_correo = Gtk.Entry(placeholder_text="Correo", hexpand=True); self.u_nombre = Gtk.Entry(placeholder_text="Nombre", hexpand=True)
        self.u_rol = Gtk.DropDown.new_from_strings(auth.ROLES); self.u_rol.set_selected(1)
        self.u_clave = Gtk.PasswordEntry(placeholder_text="Clave (mín. 8)", show_peek_icon=True)
        b = Gtk.Button(label="Crear"); b.add_css_class("suggested-action"); b.connect("clicked", self.crear_usuario)
        for w in (self.u_correo, self.u_nombre, self.u_rol, self.u_clave, b): f.append(w)
        B.append(f); self.u_msg = lbl("", "mu"); B.append(self.u_msg)
        self.u_lista = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6); B.append(self.u_lista)

    def crear_usuario(self, *_):
        ok, msg = auth.crear(self.u_correo.get_text(), self.u_nombre.get_text(), auth.ROLES[self.u_rol.get_selected()],
                             self.u_clave.get_text(), por=self.usuario["correo"])
        self.u_msg.set_label(msg)
        if ok:
            for e in (self.u_correo, self.u_nombre, self.u_clave): e.set_text("")
            self.refrescar_usuarios()

    def refrescar_usuarios(self):
        L = self.u_lista; limpiar(L)
        L.append(lbl("USUARIOS", "titulo"))
        for correo, nombre, rol, activo, creado in auth.listar():
            card = Gtk.Box(spacing=10); card.add_css_class("card")
            card.append(lbl(f"{nombre} · {correo}")); card.append(Gtk.Box(hexpand=True)); card.append(pill("ok" if activo else "off", rol if activo else rol + " · desactivado"))
            if correo != self.usuario["correo"]:
                b = Gtk.Button(label="Desactivar" if activo else "Activar")
                b.connect("clicked", lambda _b, c=correo, a=activo: (auth.activar(c, not a, self.usuario["correo"]), self.refrescar_usuarios()))
                card.append(b)
            L.append(card)
        L.append(lbl("ÚLTIMOS ACCESOS", "titulo"))
        for t, correo, ev, det in auth.accesos(40):
            r = Gtk.Box(spacing=12); r.append(lbl(fecha(t), "mu")); r.append(lbl(ev, "er" if "fallo" in ev else "ok" if ev == "login_ok" else "mu"))
            r.append(lbl(correo)); r.append(lbl(det, "mu")); L.append(r)

    def estado_sis(self, nom, d):
        nodos = [n for n in d["nodos"] if nom in nombres(n)]
        al = [a for a in d["alarmas"] if a["sistema"] == nom]
        if not nodos: return "off", "Sin nodo"
        if not any(n["conectado"] for n in nodos): return "off", "Sin conexión"
        mx = max([-1] + [sev(a["sev"]) for a in al])
        return ("er", "Falla") if mx >= 2 else ("wa", "Aviso") if mx == 1 else ("ok", "Operativo")

    def al_elegir(self, lb, row):
        if self._recon or row is None: return
        self.sel_sis = row.nombre; self.pintar_detalle(self.ult)

    def tick(self):
        if not self.usuario:
            return False
        self.refrescar(); return True

    def pintar_detalle(self, d):
        D = self.detalle; limpiar(D)
        n = self.sel_sis
        if not n:
            D.append(lbl("Elige un sistema de la lista.", "mu")); return
        c, t = self.estado_sis(n, d)
        r = Gtk.Box(spacing=10); r.append(lbl(n, "proyecto")); r.append(pill(c, t)); D.append(r)
        for x in [x for x in d["nodos"] if n in nombres(x)]:
            D.append(lbl(f"Nodo {x['direccion']} · {'conectado' if x['conectado'] else 'desconectado'} · último contacto hace {hace(d['ahora'] - x['ultimo_contacto'])}", "mu"))
        D.append(lbl("MEDICIONES", "titulo"))
        ms = [m for m in d["muestras"] if m["sistema"] == n]
        if not ms: D.append(lbl("Sin mediciones todavía.", "mu"))
        for m in ms:
            f = Gtk.Box(); f.append(lbl(m["magnitud"].replace("_", " "))); f.append(Gtk.Box(hexpand=True)); f.append(lbl(f"{m['valor']} {m['unidad'] or ''}")); D.append(f)
        D.append(lbl("ALARMAS ACTIVAS", "titulo"))
        al = [a for a in d["alarmas"] if a["sistema"] == n]
        if not al: D.append(lbl("Sin alarmas activas.", "mu"))
        for a in al:
            s = sev(a["sev"]); f = Gtk.Box(spacing=10); f.append(pill(SEV_C[s], SEV_T[s] + (" · reconocida" if a["reconocida"] else "")))
            f.append(lbl(a["detalle"] or "")); f.append(lbl(fecha(a["t"]), "mu")); D.append(f)
        D.append(lbl("HISTORIAL DE ALARMAS", "titulo"))
        hs = [h for h in d["historial"] if h["sistema"] == n]
        if not hs: D.append(lbl("Sin alarmas cerradas.", "mu"))
        for h in hs:
            f = Gtk.Box(spacing=10); f.append(lbl(f"{fecha(h['t'])} → {fecha(h['cerrada_en'])}", "mu")); f.append(lbl(h["detalle"] or "")); D.append(f)
        D.append(lbl("REGISTROS", "titulo"))
        ls = [x for x in d["logs"] if x["sistema"] == n]
        if not ls: D.append(lbl("Sin registros.", "mu"))
        for x in ls:
            s = sev(x["sev"]); f = Gtk.Box(spacing=10); f.append(lbl(fecha(x["t"]), "mu")); f.append(lbl(SEV_T[s], SEV_C[s])); f.append(lbl(x["msg"] or "")); D.append(f)

    def refrescar(self):
        try:
            d = ui.estado()
        except Exception as e:
            self.bt.set_label("Sin acceso a la base local"); self.bs.set_label(str(e)); return
        self.ult = d
        self.sub.set_label(f"Inventor Technology · Condominio {d['condominio']} · Proyecto Atalaya")
        noms = sorted({n for x in d["nodos"] for n in nombres(x)})
        est = [self.estado_sis(n, d)[0] for n in noms]
        cl, tit, sub = "off", "Sin nodos conectados", "Esperando a los nodos del condominio."
        if noms:
            if "er" in est: cl, tit = "er", "Hay fallas en el sistema"
            elif "off" in est: cl, tit = "wa", "Parte del sistema sin conexión"
            elif "wa" in est: cl, tit = "wa", "Sistema operativo con avisos"
            else: cl, tit = "ok", "Todo el sistema operativo"
            sub = f"{est.count('ok')} de {len(est)} sistemas operativos · {len(d['alarmas'])} alarmas activas"
        enlace = (f"Sin enlace con Negra / pendientes por enviar: {d['pendientes']}" if d["pendientes"] else
                  "Enlace con Negra: al día" + (f" · último envío hace {hace(d['ahora'] - d['ultimo_envio'])}" if d["ultimo_envio"] else ""))
        for c in ("ok", "wa", "er", "off"): self.banner.remove_css_class(c); self.bt.remove_css_class(c)
        self.banner.add_css_class(cl); self.bt.add_css_class(cl); self.bt.set_label(tit); self.bs.set_label(f"{sub}  ·  {enlace}")
        for c in self.cajas.values(): limpiar(c)
        # lista lateral de sistemas (dinámica)
        self._recon = True
        limpiar(self.lista)
        if self.sel_sis not in noms: self.sel_sis = noms[0] if noms else None
        for n in noms:
            c, t = self.estado_sis(n, d)
            fila = Gtk.Box(spacing=8, margin_top=8, margin_bottom=8, margin_start=8, margin_end=8)
            fila.append(lbl(n, "sis")); fila.append(Gtk.Box(hexpand=True)); fila.append(pill(c, t))
            self.lista.append(fila)
            row = self.lista.get_row_at_index(len(self.lista_filas()) - 1); row.nombre = n
            if n == self.sel_sis: self.lista.select_row(row)
        self._recon = False
        self.pintar_detalle(d)
        # Resumen
        R = self.cajas["res"]; R.append(lbl("SISTEMAS", "titulo"))
        if not noms: R.append(lbl("Aún no hay sistemas. Aparecerán cuando se conecten los nodos.", "mu"))
        fl = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE, max_children_per_line=3, column_spacing=10, row_spacing=10, homogeneous=True)
        for n in noms:
            c, t = self.estado_sis(n, d)
            card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4); card.add_css_class("card")
            r = Gtk.Box(spacing=8); r.append(lbl(n, "sis")); r.append(Gtk.Box(hexpand=True)); r.append(pill(c, t)); card.append(r)
            na = sum(1 for a in d["alarmas"] if a["sistema"] == n)
            card.append(lbl(f"{na} alarma(s) activa(s)" if na else "Sin alarmas", "mu"))
            for m in [m for m in d["muestras"] if m["sistema"] == n]:
                f = Gtk.Box(); f.append(lbl(m["magnitud"].replace("_", " "), "mu")); f.append(Gtk.Box(hexpand=True)); f.append(lbl(f"{m['valor']} {m['unidad'] or ''}")); card.append(f)
            fl.append(card)
        R.append(fl)
        # Alarmas
        A = self.cajas["al"]; A.append(lbl("ALARMAS ACTIVAS", "titulo"))
        if not d["alarmas"]: A.append(lbl("Sin alarmas activas.", "mu"))
        for x in d["alarmas"]:
            s = sev(x["sev"]); card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL); card.add_css_class("card")
            r = Gtk.Box(spacing=8); r.append(lbl(f"{x['sistema']}: {x['detalle'] or ''}", wrap=True)); r.append(Gtk.Box(hexpand=True))
            r.append(pill(SEV_C[s], SEV_T[s] + (" · reconocida" if x["reconocida"] else ""))); card.append(r); card.append(lbl(fecha(x["t"]), "mu")); A.append(card)
        A.append(lbl("HISTORIAL DE ALARMAS", "titulo"))
        if not d["historial"]: A.append(lbl("Sin alarmas cerradas.", "mu"))
        for x in d["historial"]:
            s = sev(x["sev"]); r = Gtk.Box(spacing=12); r.append(lbl(f"{fecha(x['t'])} → {fecha(x['cerrada_en'])}", "mu"))
            r.append(lbl(SEV_T[s], SEV_C[s])); r.append(lbl(f"{x['sistema']}: {x['detalle'] or ''}")); A.append(r)
        # Registros
        L = self.cajas["lg"]; L.append(lbl("ÚLTIMOS REGISTROS", "titulo"))
        if not d["logs"]: L.append(lbl("Sin registros.", "mu"))
        for x in d["logs"]:
            s = sev(x["sev"]); r = Gtk.Box(spacing=12); r.append(lbl(fecha(x["t"]), "mu")); r.append(lbl(SEV_T[s], SEV_C[s]))
            r.append(lbl(x["sistema"] or "")); r.append(lbl(x["msg"] or "")); L.append(r)
        # Nodos
        N = self.cajas["nd"]; N.append(lbl("NODOS", "titulo"))
        if not d["nodos"]: N.append(lbl("Ningún nodo se ha conectado todavía.", "mu"))
        for x in d["nodos"]:
            card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL); card.add_css_class("card")
            r = Gtk.Box(spacing=8); r.append(lbl(", ".join(nombres(x)) or x["nodo"], "sis")); r.append(Gtk.Box(hexpand=True))
            r.append(pill("ok" if x["conectado"] else "er", "conectado" if x["conectado"] else "desconectado")); card.append(r)
            card.append(lbl(f"{x['direccion']} · último contacto hace {hace(d['ahora'] - x['ultimo_contacto'])}", "mu")); N.append(card)

    def lista_filas(self):
        out, h = [], self.lista.get_first_child()
        while h:
            out.append(h); h = h.get_next_sibling()
        return out


class App(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="pe.inventor.atalaya")

    def do_activate(self):
        prov = Gtk.CssProvider(); prov.load_from_data(CSS)
        Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), prov, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        Gtk.Settings.get_default().set_property("gtk-application-prefer-dark-theme", True)
        (self.props.active_window or Ventana(self)).present()


if __name__ == "__main__":
    sys.exit(App().run(sys.argv[:1]))
