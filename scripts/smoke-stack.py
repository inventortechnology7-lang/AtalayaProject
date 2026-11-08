#!/usr/bin/env python3
"""Real local TCP -> SQLite -> HTTP -> PostgreSQL, command and outage/restart test.
Requires the project's compose stack. Stops only its backend/edge services.
"""
import json
import socket
import subprocess
import time
import urllib.request
import urllib.error
import urllib.parse
import http.cookiejar
import uuid
import tempfile
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
env=dict(line.split('=',1) for line in (ROOT/'.env').read_text().splitlines() if '=' in line and not line.startswith('#'))
BASE='http://127.0.0.1:28080'

def api(path,body=None,token=None):
    headers={'Content-Type':'application/json'}
    if token: headers['Authorization']='Bearer '+token
    req=urllib.request.Request(BASE+path,data=json.dumps(body).encode() if body is not None else None,headers=headers)
    with urllib.request.urlopen(req,timeout=10) as r: return json.loads(r.read() or b'{}')

def until(fn,seconds=90):
    end=time.monotonic()+seconds
    while time.monotonic()<end:
        try:
            result=fn()
            if result:return result
        except (OSError,ValueError):pass
        time.sleep(.5)
    raise AssertionError('Timed out waiting for stack condition')

def compose(*args):subprocess.run(['docker','compose',*args],cwd=ROOT,check=True,stdout=subprocess.DEVNULL)

def node():
    sock=socket.create_connection(('127.0.0.1',8300),timeout=5)
    f=sock.makefile('rwb');f.write(('TOKEN '+env['PLACA_TOKEN']+'\n').encode());f.flush()
    assert f.readline().startswith(b'HORA ')
    send(f,{'cfg':{'cor':['Puertas']}})
    send(f,{'st':{'pue':'A','puerta':'diagnostico','el':[0,0,0],'al':[]}})
    return sock,f

def send(f,payload):f.write(json.dumps(payload).encode()+b'\n');f.flush()

until(lambda:api('/health'))
admin=api('/api/login',{'correo':env['ADMIN_EMAIL'],'clave':env['ADMIN_PASSWORD']})['token']
first='smoke-'+uuid.uuid4().hex
sock,f=node()
send(f,{'log':{'t':time.time(),'v':0,'s':'Puertas','m':first}})
until(lambda:any(r['mensaje']==first for r in api('/api/dashboard',token=admin)['logs']))
api('/api/comandos',{'destino':'puerta-A','linea':'ORDEN','origen':'web'},admin)
sock.settimeout(20)
for _ in range(5):
    line=f.readline()
    if line==b'ORDEN\n':break
else:raise AssertionError('Physical command did not reach test TCP client')
print('PASS TCP ingestion, authenticated sync and SSE command delivery')
second='offline-'+uuid.uuid4().hex
try:
    compose('stop','backend')
    send(f,{'log':{'t':time.time(),'v':0,'s':'Puertas','m':second}})
    time.sleep(2)
    local=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    form=urllib.parse.urlencode({'correo':env['LOCAL_UI_EMAIL'],'clave':env['LOCAL_UI_PASSWORD']}).encode()
    with local.open('http://127.0.0.1:28082/login',form,timeout=10) as r: assert r.status==200
    with local.open('http://127.0.0.1:28082/api/estado',timeout=10) as r:
        state=json.load(r)
        assert state['pendientes']>0
        assert any(row['msg']==second for row in state['logs'])
    print('PASS authenticated local dashboard remains available offline')
    f.close();sock.close()
    compose('restart','edge')
    time.sleep(2)
finally:
    compose('start','backend')
until(lambda:api('/health'))
until(lambda:any(r['mensaje']==second for r in api('/api/dashboard',token=admin)['logs']),120)
rows=api('/api/dashboard',token=admin)['logs']
assert sum(r['mensaje']==second for r in rows)==1
assert sum(r['mensaje']==first for r in rows)==1
print('PASS offline queue survives edge restart and syncs without duplication')
# Import an actual SQLite backup twice; replay must not create additional records.
compose('exec','-T','edge','python','-c',"import sqlite3; src=sqlite3.connect('/data/katana.db'); dst=sqlite3.connect('/tmp/import-backup.db'); src.backup(dst); dst.close(); src.close()")
with tempfile.TemporaryDirectory() as directory:
    backup=Path(directory)/'katana.db'
    with backup.open('wb') as output:
        subprocess.run(['docker','compose','exec','-T','edge','cat','/tmp/import-backup.db'],cwd=ROOT,stdout=output,check=True)
    command=[sys.executable,str(ROOT/'scripts/import-sqlite.py'),str(backup),'--url',BASE,'--condominio','1','--env-file',str(ROOT/'.env')]
    subprocess.run(command,check=True)
    subprocess.run(command+['--apply'],check=True)
    before=api('/api/dashboard',token=admin)
    subprocess.run(command+['--apply'],check=True)
    after=api('/api/dashboard',token=admin)
    for kind in ('alarmas','logs','muestras'):
        assert {r['uid'] for r in before[kind]}=={r['uid'] for r in after[kind]}
print('PASS read-only historical import is repeatable without duplicate UIDs')
api('/api/logout',{},admin)
