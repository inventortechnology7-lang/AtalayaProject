"""Pruebas de puertas A/B (orden #006): python3 -m unittest -v test_puertas.py"""
import json, os, sqlite3, tempfile, time, unittest
import receptor


class Escritor:
    def __init__(self): self.lineas = []
    def write(self, b): self.lineas += b.decode().splitlines()


class Puertas(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        receptor.ALM = receptor.Almacen(os.path.join(self.dir.name, "k.db"))
        self.pant = Escritor(); receptor.PANTALLAS.clear(); receptor.PANTALLAS.add(self.pant)
        self.A = "172.27.198.129"
        self.sis = receptor.procesar(self.A, self.A + ":1", [], {"cfg": {"cor": ["Puertas"]}})

    def tearDown(self):
        receptor.PANTALLAS.clear(); receptor.ALM.db.close(); self.dir.cleanup()

    def st(self, el, al=(), puerta="cerrada", pue="A", nodo=None):
        receptor.procesar(nodo or self.A, "x", self.sis,
                          {"st": {"al": list(al), "pue": pue, "puerta": puerta, "el": el, "up": 5}})

    def alarmas(self):
        return receptor.ALM.db.execute("SELECT detalle, sev FROM alarmas WHERE abierta=1").fetchall()

    def test_el_va_a_la_pantalla_solo_al_cambiar(self):
        self.st([0, 0, 0])
        self.assertEqual(self.pant.lineas, ["EL 30 0", "EL 31 0", "EL 32 0"])
        self.st([0, 0, 0]); self.assertEqual(len(self.pant.lineas), 3)
        self.st([0, 0, 1], al=[[0, 2, 0, 1794090000, "Puerta A: motor"]], puerta="trabada")
        self.assertEqual(self.pant.lineas[-3:], ["EL 30 0", "EL 31 0", "EL 32 1"])
        self.assertEqual(self.alarmas(), [("Puerta A: motor", 2)])
        fila = receptor.ALM.db.execute("SELECT puerta, el FROM puertas WHERE pue='A'").fetchone()
        self.assertEqual(fila, ("trabada", "[0, 0, 1]"))

    def test_puerta_b_usa_indices_33_35(self):
        self.st([1, 0, 0], pue="B", nodo="172.27.198.65")
        self.assertEqual(self.pant.lineas, ["EL 33 1", "EL 34 0", "EL 35 0"])

    def test_nodo_caido_y_vuelta(self):
        self.st([0, 0, 0]); self.pant.lineas.clear()
        nuevas = receptor.ALM.puertas_caidas(time.time() + 121)
        for p in nuevas: receptor.a_pantallas(receptor.lineas_el(p, [1, 1, 1]))
        self.assertEqual(nuevas, ["A"])
        self.assertEqual(self.alarmas(), [("Puerta A sin comunicacion", 2)])
        self.assertEqual(self.pant.lineas, ["EL 30 1", "EL 31 1", "EL 32 1"])
        self.assertEqual(receptor.ALM.puertas_caidas(time.time() + 300), [])        # no duplica
        self.assertIn("Puerta A sin comunicacion",
                      [r[0] for r in receptor.ALM.db.execute("SELECT msg FROM logs")])
        self.st([0, 0, 0])                                                         # vuelve
        self.assertEqual(self.alarmas(), [])
        self.assertEqual(self.pant.lineas[-3:], ["EL 30 0", "EL 31 0", "EL 32 0"])
        tipos = [r[0] for r in receptor.ALM.db.execute("SELECT tipo FROM outbox")]
        self.assertGreaterEqual(tipos.count("alarma"), 2)                          # apertura y cierre a Negra

    def test_pantalla_recibe_estado_al_conectar(self):
        self.st([0, 1, 0])
        self.assertEqual(receptor.ALM.els_actuales(), [(30, 0), (31, 1), (32, 0)])

    def test_nodo_no_pisa_pantalla(self):
        self.st([0, 0, 0])
        self.assertIsNone(receptor.ALM.db.execute("SELECT * FROM pantalla").fetchone())


if __name__ == "__main__":
    unittest.main()
