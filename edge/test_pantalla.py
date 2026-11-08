"""Pruebas del reenvío de pantalla (python3 -m unittest -v test_pantalla.py)."""
import json, os, sqlite3, tempfile, unittest
import receptor, sync


class Falso:
    def __init__(self, falla=False):
        self.envios, self.falla = [], falla

    def pantalla(self, cfg, st):
        if self.falla:
            raise sync.ErrorHttp(502)
        self.envios.append((cfg, st))


class Pantalla(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.ruta = os.path.join(self.dir.name, "k.db")
        receptor.ALM = receptor.Almacen(self.ruta)
        self.db = sqlite3.connect(self.ruta)

    def tearDown(self):
        self.db.close(); receptor.ALM.db.close(); self.dir.cleanup()

    def version(self):
        return self.db.execute("SELECT version FROM pantalla WHERE id=1").fetchone()[0]

    def test_guarda_y_sube_version_solo_si_cambia(self):
        receptor.procesar("127.0.0.1", "n:1", [], {"cfg": {"cor": ["P1"]}, "st": {"al": [], "red": 3}})
        self.assertEqual(self.version(), 1)
        receptor.procesar("127.0.0.1", "n:1", ["P1"], {"st": {"red": 3, "al": []}})   # mismo st, otro orden
        self.assertEqual(self.version(), 1)
        receptor.procesar("127.0.0.1", "n:1", ["P1"], {"st": {"al": [], "red": 2}})
        self.assertEqual(self.version(), 2)
        cfg, st = self.db.execute("SELECT cfg, st FROM pantalla").fetchone()
        self.assertEqual(json.loads(cfg), {"cor": ["P1"]})          # cfg previo se conserva
        self.assertEqual(json.loads(st)["red"], 2)

    def test_nodo_de_red_no_pisa_la_pantalla(self):
        receptor.procesar("127.0.0.1", "127.0.0.1:5", [], {"cfg": {"cor": ["CAM"]}, "st": {"al": []}})
        sis = receptor.procesar("172.27.198.129", "172.27.198.129:9", [], {"cfg": {"cor": ["Puertas"]}})
        receptor.procesar("172.27.198.129", "172.27.198.129:9", sis, {"st": {"al": [[0, 2, 0, 1794090000, "Puerta A"]]}})
        cfg, nodo = self.db.execute("SELECT cfg, nodo FROM pantalla").fetchone()
        self.assertEqual((json.loads(cfg), nodo, self.version()), ({"cor": ["CAM"]}, "127.0.0.1", 1))
        al = self.db.execute("SELECT nodo, sistema FROM alarmas").fetchall()
        self.assertEqual(al, [("172.27.198.129", "Puertas")])      # sus alarmas sí se guardan

    def test_ignora_mensajes_sin_pantalla(self):
        receptor.procesar("127.0.0.1", "n:1", [], {"logs": [[1, 0, "P1", "x"]]})
        self.assertIsNone(self.db.execute("SELECT * FROM pantalla").fetchone())

    def test_envia_una_vez_por_version(self):
        e = Falso()
        self.assertIsNone(sync.enviar_pantalla(e, self.db, None))     # sin pantalla aún
        receptor.procesar("127.0.0.1", "n:1", [], {"cfg": {"a": 1}})
        v = sync.enviar_pantalla(e, self.db, None)
        self.assertEqual(sync.enviar_pantalla(e, self.db, v), v)
        self.assertEqual(e.envios, [({"a": 1}, None)])

    def test_falla_no_marca_enviado(self):
        receptor.procesar("127.0.0.1", "n:1", [], {"st": {"x": 1}})
        with self.assertRaises(sync.ErrorHttp):
            sync.enviar_pantalla(Falso(falla=True), self.db, None)
        e = Falso()
        sync.enviar_pantalla(e, self.db, None)                        # al reconectar se reenvía
        self.assertEqual(e.envios, [(None, {"x": 1})])

    def test_tabla_inexistente(self):
        db = sqlite3.connect(":memory:")
        self.assertEqual(sync.enviar_pantalla(Falso(), db, 7), 7)


if __name__ == "__main__":
    unittest.main()
