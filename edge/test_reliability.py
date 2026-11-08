import asyncio
import json
import os
import tempfile
import unittest
from unittest.mock import patch
import receptor
import sync

class Reliability(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmp.name, 'edge.db')
        self.store = receptor.Almacen(self.path)
    def tearDown(self):
        self.store.db.close()
        self.tmp.cleanup()
    def test_outbox_failure_rolls_back_event(self):
        with patch.object(self.store, '_outbox', side_effect=RuntimeError('disk full')):
            with self.assertRaises(RuntimeError):
                self.store.log('node', 1, 0, 'Puertas', 'event')
        self.assertEqual(self.store.db.execute('SELECT count(*) FROM logs').fetchone()[0], 0)
    def test_restart_and_retry_preserve_uid(self):
        self.store.log('node', 1, 0, 'Puertas', 'event')
        self.store.db.close()
        self.store = receptor.Almacen(self.path)
        rows = self.store.db.execute('SELECT id,uid,tipo,payload,creado FROM outbox').fetchall()
        class Offline:
            def enviar(self, rows): raise sync.ErrorHttp(503)
        with self.assertRaises(sync.ErrorHttp): sync.enviar_filas(Offline(), self.store.db, rows)
        self.assertIsNone(self.store.db.execute('SELECT enviado FROM outbox').fetchone()[0])
        class Online:
            def enviar(self, rows): return {'nuevos': len(rows)}
        sync.enviar_filas(Online(), self.store.db, rows)
        self.assertGreater(self.store.db.execute('SELECT enviado FROM outbox').fetchone()[0], 0)
        self.store.log('node', 1, 0, 'Puertas', 'event')
        self.assertEqual(self.store.db.execute('SELECT count(*) FROM outbox').fetchone()[0], 1)
    def test_bad_record_isolated(self):
        for i in range(3): self.store.log('node', i, 0, 'Puertas', str(i))
        rows = self.store.db.execute('SELECT id,uid,tipo,payload,creado FROM outbox ORDER BY id').fetchall()
        class Reject:
            def enviar(self, batch):
                if any(json.loads(row[3])['msg']=='1' for row in batch): raise sync.ErrorHttp(400)
        self.assertEqual(len(sync.enviar_filas(Reject(), self.store.db, rows)), 2)
        self.assertEqual(self.store.db.execute('SELECT count(*) FROM outbox WHERE enviado=-1').fetchone()[0], 1)

class TCP(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        receptor.ALM=receptor.Almacen(os.path.join(self.tmp.name,'edge.db'))
        receptor.TOKEN='test-token'; receptor.PANTALLA_ORIGEN=set()
        self.server=await asyncio.start_server(receptor.atender,'127.0.0.1',0,limit=receptor.MAX_LINEA)
        self.port=self.server.sockets[0].getsockname()[1]
    async def asyncTearDown(self):
        self.server.close(); await self.server.wait_closed()
        await asyncio.sleep(.05)
        receptor.ALM.db.close(); self.tmp.cleanup()
    async def test_auth_framing_and_order(self):
        r,w=await asyncio.open_connection('127.0.0.1',self.port)
        w.write(b'TOKEN bad\n'); await w.drain()
        self.assertEqual(await asyncio.wait_for(r.read(),1),b'');w.close(); await w.wait_closed()
        r,w=await asyncio.open_connection('127.0.0.1',self.port)
        w.write(b'TOKEN test-token\n');await w.drain()
        self.assertTrue((await r.readline()).startswith(b'HORA '))
        w.write(b'broken\n{"cfg":{"cor":["Puertas"]}}\n{"st":{"pue":"A","el":[0,0,0],"al":[]}}\n');await w.drain()
        for _ in range(50):
            if receptor.ALM.nodo_de_puerta('A')[0]: break
            await asyncio.sleep(.01)
        ok,_=await receptor.entregar_orden('A','ORDEN','web','1')
        self.assertTrue(ok);self.assertEqual(await r.readline(),b'ORDEN\n')
        w.close();await w.wait_closed()
