#!/usr/bin/env python3
"""Exercises ONLY an explicitly selected isolated Katana stack; no physical commands."""
import json, os, socket, time, urllib.request, uuid
from pathlib import Path
values={}
for line in Path(os.environ.get('KATANA_ENV_FILE','.env')).read_text().splitlines():
    if '=' in line and not line.startswith('#'):
        key,value=line.split('=',1);values[key]=value
base=os.environ.get('KATANA_TEST_URL','http://127.0.0.1:28182')
port=int(os.environ.get('KATANA_TCP_PORT','18300'))
host=os.environ.get('KATANA_TCP_HOST','127.0.0.1')
if port==8300 and not os.environ.get('KATANA_ALLOW_TEST_PORT'): raise SystemExit('Refusing operational TCP port; use an isolated stack')
def api(path,body=None,token=None,method=None):
    request=urllib.request.Request(base+'/api/local'+path,None if body is None else json.dumps(body).encode(),headers={'Content-Type':'application/json',**({'Authorization':'Bearer '+token} if token else {})},method=method)
    with urllib.request.urlopen(request,timeout=10) as response:
        raw=response.read();return json.loads(raw) if raw else None
session=api('/auth/login',{'email':values['ADMIN_EMAIL'],'password':values['ADMIN_PASSWORD']})['token']
with socket.create_connection((host,port),timeout=3) as bad:
    bad.sendall(b'TOKEN incorrect\n');assert not bad.recv(1)
message='katana-smoke-'+uuid.uuid4().hex
with socket.create_connection((host,port),timeout=5) as board:
    board.sendall(('TOKEN '+values['PLACA_TOKEN']+'\n').encode());stream=board.makefile('rb');assert stream.readline().startswith(b'HORA ')
    payload={'cfg':{'cor':['Puertas']},'st':{'pue':'A','puerta':'cerrada','el':[0,1,0],'al':[[0,2,0,1794091234,'Prueba aislada Sensor 2']]},'log':{'t':1794091234,'v':1,'s':'Puertas','m':message},'m':[['Puertas','voltaje',12.3,'V']]}
    board.sendall((json.dumps(payload)+'\n'+json.dumps(payload)+'\n').encode())
    for _ in range(50):
        logs=api('/logs?q='+message,token=session)
        if logs['total']==1:break
        time.sleep(.1)
    assert logs['total']==1
    board.sendall((json.dumps({'st':{'pue':'B','puerta':'abierta','el':[0,0,0],'al':payload['st']['al']}})+'\n').encode())
    time.sleep(.3)
    dashboard=api('/dashboard',token=session);assert len(dashboard['doors'])==2
    with urllib.request.urlopen(urllib.request.Request(base+'/api/local/events',headers={'Authorization':'Bearer '+session}),timeout=5) as events:
        def event():
            lines=[]
            while True:
                line=events.readline()
                if not line: raise AssertionError('SSE disconnected')
                if line in (b'\n',b'\r\n'): return b''.join(lines)
                lines.append(line)
        first=event();assert b'event:state' in first
        board.sendall((json.dumps({'cfg':{'cor':['Puertas'],'version':message}})+'\n').encode())
        first_id=next(line for line in first.splitlines() if line.startswith(b'id:'))
        for _ in range(4):
            update=event()
            if first_id not in update.splitlines(): break
        else: raise AssertionError('No committed update delivered through SSE')
    assert api('/alarms?active=true',token=session)['total']>=1
    assert api('/telemetry',token=session)['total']>=2
    assert api('/history',token=session)['total']>=2
    # Host TCP source must be explicitly configured as a screen for this verification.
    if os.environ.get('KATANA_EXPECT_EL')=='true':
        seen=set()
        for _ in range(30):
            line=stream.readline().decode().strip()
            if line.startswith('EL '):seen.add(int(line.split()[1]))
            if len(seen)==6:break
        assert seen==set(range(30,36)),seen
    stream.close()
for _ in range(50):
    doors=api('/doors',token=session)
    if all(d['unavailable'] for d in doors):break
    time.sleep(.1)
assert all(d['unavailable'] for d in doors)
assert next(d for d in doors if d['id']=='A')['sensor_1']==0
api('/auth/logout',{},token=session)
print('PASS: authenticated TCP, cfg/st/log/m, UID deduplication, A/B, SSE, disconnect semantics'+(', EL 30–35' if os.environ.get('KATANA_EXPECT_EL') else ''))
