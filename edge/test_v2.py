import json
import os
import tempfile
import time
import unittest
from datetime import datetime, timezone
from unittest.mock import patch
import receptor
import ordenes
import sync

class V2(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.store=receptor.Almacen(os.path.join(self.tmp.name,'test.db'))
        self.db=self.store.db
        self.db.executescript(ordenes.SCHEMA)
    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()
    def command(self,expiry):
        self.db.execute("INSERT INTO ordenes_web(id,destino,linea,crudo) VALUES(1,'puerta-A','ORDEN',?)",(json.dumps({'expires':expiry}),))
        self.db.commit()
    def test_expired_or_missing_commands_never_reach_socket(self):
        for expiry in ('', '2000-01-01T00:00:00Z'):
            self.db.execute('DELETE FROM ordenes_web')
            self.command(expiry)
            with patch.object(ordenes,'al_receptor') as send:
                ordenes.entregar_pendientes(self.db)
                send.assert_not_called()
    def test_uncertain_delivery_is_never_retried(self):
        self.command(datetime.fromtimestamp(time.time()+30,timezone.utc).isoformat())
        with patch.object(ordenes,'al_receptor',return_value=(None,'timeout')) as send:
            ordenes.entregar_pendientes(self.db)
            ordenes.entregar_pendientes(self.db)
            self.assertEqual(send.call_count,1)
    def test_crash_after_claim_is_never_replayed(self):
        self.command(datetime.fromtimestamp(time.time()+30,timezone.utc).isoformat())
        with patch.object(ordenes,'al_receptor',side_effect=RuntimeError('crash')):
            with self.assertRaises(RuntimeError):ordenes.entregar_pendientes(self.db)
        with patch.object(ordenes,'al_receptor') as send:
            ordenes.entregar_pendientes(self.db)
            send.assert_not_called()
    def test_door_state_and_outbox_are_atomic(self):
        with patch.object(self.store,'_outbox',side_effect=RuntimeError('disk full')):
            with self.assertRaises(RuntimeError): self.store.puerta('test',{'pue':'A','puerta':'cerrada'})
        self.assertEqual(self.db.execute('SELECT count(*) FROM puertas').fetchone()[0],0)
    def test_independent_states_survive_offline_queue(self):
        self.store.puerta('a',{'pue':'A','puerta':'cerrada','el':[0,0,0]})
        self.store.puerta('b',{'pue':'B','puerta':'trabada','el':[0,0,1]})
        rows=self.db.execute('SELECT id,uid,tipo,payload,creado FROM outbox').fetchall()
        batch=sync.armar(rows)
        self.assertEqual({d['pue']:d['puerta'] for d in batch['puertas']},{'A':'cerrada','B':'trabada'})
        self.assertTrue(all(d['uid'] and d['t'] for d in batch['puertas']))
