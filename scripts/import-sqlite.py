#!/usr/bin/env python3
"""Replay a backed-up Katana database into the compatible API without changing it.
Dry-run by default. Credentials come from SYNC_USUARIO / SYNC_CLAVE or --env-file.
Run on a SQLite backup (Connection.backup), never a partial copy of a live WAL file.
"""
import argparse
import importlib.util
import json
import os
import sqlite3
import time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('katana_sync',ROOT/'edge/sync.py')
sync=importlib.util.module_from_spec(spec);spec.loader.exec_module(sync)

def rows(db):
    for uid,nodo,sistema,sev,ack,t,detalle,abierta,cerrada in db.execute('SELECT uid,nodo,sistema,sev,reconocida,t,detalle,abierta,cerrada_en FROM alarmas ORDER BY rowid'):
        yield 'alarma',dict(uid=uid,nodo=nodo,sistema=sistema,sev=sev,reconocida=bool(ack),t=t,detalle=detalle,abierta=bool(abierta),cerrada_en=cerrada)
    for uid,nodo,t,sev,sistema,msg in db.execute('SELECT uid,nodo,t,sev,sistema,msg FROM logs ORDER BY rowid'):
        yield 'log',dict(uid=uid,nodo=nodo,t=t,sev=sev,sistema=sistema,msg=msg)
    for uid,nodo,recibido,sistema,magnitud,valor,unidad in db.execute('SELECT uid,nodo,recibido,sistema,magnitud,valor,unidad FROM muestras ORDER BY rowid'):
        yield 'muestra',dict(uid=uid,nodo=nodo,recibido=recibido,sistema=sistema,magnitud=magnitud,valor=valor,unidad=unidad)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('backup',type=Path);p.add_argument('--url',required=True)
    p.add_argument('--condominio',type=int,required=True);p.add_argument('--env-file',type=Path)
    p.add_argument('--apply',action='store_true')
    a=p.parse_args()
    env={}
    if a.env_file:
        env.update(line.split('=',1) for line in a.env_file.read_text().splitlines() if '=' in line and not line.startswith('#'))
    env.update(os.environ)
    sync.URL=a.url.rstrip('/');sync.USUARIO=env.get('SYNC_USUARIO','');sync.CLAVE=env.get('SYNC_CLAVE','');sync.CONDO_ID=a.condominio
    if a.condominio<1:p.error('condominio must be positive')
    if a.apply and not(sync.USUARIO and sync.CLAVE):p.error('sync credentials required')
    db=sqlite3.connect(a.backup.resolve().as_uri()+'?mode=ro',uri=True)
    counts={k:db.execute(f'SELECT count(*) FROM {k}').fetchone()[0] for k in ('alarmas','logs','muestras')}
    print(json.dumps({'records':counts,'mode':'apply' if a.apply else 'dry-run'}))
    if not a.apply:return
    enlace=sync.Enlace();batch=[];sent=0
    for kind,payload in rows(db):
        # Prefer original reception time when available; preserves uptime timestamp fallback.
        received=db.execute('SELECT min(creado) FROM outbox WHERE uid=? OR uid=?',(payload['uid'],payload['uid']+':a')).fetchone()[0]
        batch.append((len(batch),payload['uid'],kind,json.dumps(payload),received or payload.get('recibido') or time.time()))
        if len(batch)==500:
            enlace.enviar(batch);sent+=len(batch);batch=[]
    if batch:enlace.enviar(batch);sent+=len(batch)
    print(f'Confirmed {sent} records. Source database unchanged.')

if __name__=='__main__':main()
