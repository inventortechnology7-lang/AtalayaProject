"""Pruebas unitarias del puente (python3 -m unittest test_puente_pantalla.py)."""
import os
import tempfile
import unittest

from puente_pantalla import debe_reenviar, es_orden_pantalla, lee_token


class Filtro(unittest.TestCase):
    def test_reenvia_json_del_sistema(self):
        self.assertTrue(debe_reenviar('{"st":{"up":5}}'))
        self.assertTrue(debe_reenviar('{"log":{"t":1,"s":"PUE","m":"x","v":1}}\r'))

    def test_no_reenvia_dedo_ni_capturas(self):
        self.assertFalse(debe_reenviar('{"p":[10,20]}'))
        self.assertFalse(debe_reenviar("C12 00ff00ff"))
        self.assertFalse(debe_reenviar(""))


class Ordenes(unittest.TestCase):
    def test_acepta_hora_sync_y_estados(self):
        for o in ("SYNC", "HORA 1794084760", "EL 30 1", "EL 35 0"):
            self.assertTrue(es_orden_pantalla(o), o)

    def test_rechaza_lo_demas(self):
        for o in ("EL 30 2", "EL x 1", "EL 30", "TAP 10 10", "SHOT", ""):
            self.assertFalse(es_orden_pantalla(o), o)


class Token(unittest.TestCase):
    def test_variable_de_entorno_gana(self):
        self.assertEqual(lee_token(None, {"PLACA_TOKEN": " abc "}), "abc")

    def test_lee_archivo_env(self):
        with tempfile.NamedTemporaryFile("w", delete=False, suffix=".env") as f:
            f.write("OTRA=1\nPLACA_TOKEN=\"xyz\"\n")
        try:
            self.assertEqual(lee_token(f.name, {}), "xyz")
        finally:
            os.unlink(f.name)

    def test_sin_token(self):
        self.assertEqual(lee_token(None, {}), "")


if __name__ == "__main__":
    unittest.main()
