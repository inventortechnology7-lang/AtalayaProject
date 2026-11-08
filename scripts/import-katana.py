#!/usr/bin/env python3
"""Offline migration into a NEW Katana database. Requires a verified backup manifest.
Uses psql inside an explicitly selected local Docker container; never calls central APIs.
Legacy passwords are not imported: accounts require a controlled reset.
"""
import argparse
import datetime as dt
import hashlib
import json
import pathlib
import sqlite3
import subprocess


def literal(value):
    if value is None: return 'NULL'
    if isinstance(value, bool): return 'true' if value else 'false'
    if isinstance(value, (int, float)): return str(value)
    return "'" + str(value).replace("'", "''") + "'"


def timestamp(value, fallback):
    if value is None: return fallback
    value = float(value)
    if value > 1e11: value /= 1000
    if value < 1.5e9: return fallback
    return dt.datetime.fromtimestamp(value, dt.timezone.utc).isoformat()


def rows(path):
    with sqlite3.connect(f'{path.resolve().as_uri()}?mode=ro', uri=True) as db:
        db.row_factory = sqlite3.Row
        if db.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
            raise ValueError('SQLite integrity check failed')
        names = [r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
        return {name: [dict(r) for r in db.execute('SELECT rowid AS _source_rowid,* FROM "' + name.replace('"','""') + '"')] for name in names}


def plan(backup):
    manifest = json.loads((backup / 'manifest.json').read_text())
    sources = {}
    for name in ('katana.db', 'usuarios.db'):
        path = backup / name
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != manifest['files'][name]['sha256']: raise ValueError(f'Backup checksum mismatch: {name}')
        data = rows(path)
        for table, records in data.items():
            if len(records) != manifest['files'][name]['rows'][table]: raise ValueError('Backup count mismatch: '+table)
        sources[name] = (digest, data)
    sql = ["\\set ON_ERROR_STOP on", 'BEGIN;', 'SET LOCAL standard_conforming_strings = on;',
           "SELECT pg_advisory_xact_lock(8300,1);",
           "DO $$ BEGIN IF EXISTS(SELECT 1 FROM device_connections) OR EXISTS(SELECT 1 FROM sessions) THEN RAISE EXCEPTION 'Import requires an unused offline target'; END IF; IF NOT EXISTS(SELECT 1 FROM import_runs) AND (EXISTS(SELECT 1 FROM devices) OR EXISTS(SELECT 1 FROM users) OR EXISTS(SELECT 1 FROM audit_logs) OR EXISTS(SELECT 1 FROM legacy_records)) THEN RAISE EXCEPTION 'Initial import requires an empty target'; END IF; END $$;"]
    fallback = dt.datetime.fromtimestamp((backup/'katana.db').stat().st_mtime,dt.timezone.utc).isoformat()
    def insert(table, values, conflict='ON CONFLICT DO NOTHING'):
        sql.append(f"INSERT INTO {table} ({','.join(values)}) VALUES ({','.join(literal(v) for v in values.values())}) {conflict};")
    def encoded(value): return json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(',',':'))
    digest, data = sources['katana.db']
    allowed = ','.join(literal(d) for d,_ in sources.values())
    sql.append('SELECT 1 / CASE WHEN NOT EXISTS(SELECT 1 FROM import_runs WHERE source_sha256 NOT IN ('+allowed+')) THEN 1 ELSE 0 END;')
    known = {r['nodo']: r for r in data.get('nodos', [])}
    for table in ('alarmas','logs','muestras','puertas','pantalla'):
        for r in data.get(table,[]):
            node = r.get('nodo') or 'legacy-unassigned'
            known.setdefault(node, {'nodo':node})
    for node, r in known.items():
        systems = json.loads(r.get('sistemas') or '[]')
        insert('devices',dict(node=node,address=r.get('direccion'),systems=encoded(systems),first_seen=timestamp(r.get('primera_conexion'),fallback),last_seen=timestamp(r.get('ultimo_contacto'),fallback),connected=False))
    for r in data.get('puertas',[]):
        if r['pue'] not in ('A','B'): raise ValueError('Unsupported legacy door; source preserved, import aborted')
        node=r.get('nodo') or 'legacy-unassigned'
        insert('doors',dict(id=r['pue'],node=node))
        elements=json.loads(r.get('el') or '[]')
        if elements and (len(elements)!=3 or any(v not in (0,1) for v in elements)): raise ValueError('Unsupported legacy elements')
        elements=(elements+[None]*3)[:3]
        at=timestamp(r.get('actualizado'),fallback)
        insert('door_status',dict(door_id=r['pue'],reported_state=r.get('puerta'),sensor_1=elements[0],sensor_2=elements[1],motor=elements[2],uptime=r.get('up'),observed_at=at,last_contact=at,offline=True))
    for r in data.get('pantalla',[]):
        sql.append('UPDATE devices SET config='+literal(r.get('cfg'))+'::jsonb,screen_state='+literal(r.get('st'))+'::jsonb WHERE node='+literal(r.get('nodo') or 'legacy-unassigned')+';')
    for r in data.get('alarmas',[]):
        insert('alarms',dict(uid=r['uid'],node=r.get('nodo') or 'legacy-unassigned',system=r.get('sistema') or '',severity=r['sev'],detail=r.get('detalle') or '',source='IMPORT',board_acknowledged=bool(r.get('reconocida')),opened_at=timestamp(r.get('t'),fallback),closed_at=timestamp(r['cerrada_en'],fallback) if r.get('cerrada_en') else None,raw_time=r.get('t'),active=bool(r.get('abierta',1))))
        sql.append('INSERT INTO alarm_history(alarm_uid,kind,occurred_at,payload) SELECT '+','.join(literal(v) for v in (r['uid'],'imported',fallback,encoded(r)))+' WHERE NOT EXISTS(SELECT 1 FROM alarm_history WHERE alarm_uid='+literal(r['uid'])+" AND kind='imported');")
    for r in data.get('logs',[]):
        insert('system_logs',dict(uid=r['uid'],node=r.get('nodo') or 'legacy-unassigned',system=r.get('sistema') or '',severity=r['sev'],message=r.get('msg') or '',occurred_at=timestamp(r.get('t'),fallback),received_at=fallback,raw_time=r.get('t')))
    for r in data.get('muestras',[]):
        insert('telemetry_samples',dict(uid=r['uid'],node=r.get('nodo') or 'legacy-unassigned',system=r.get('sistema') or '',magnitude=r.get('magnitud') or '',value=r['valor'],unit=r.get('unidad') or '',received_at=timestamp(r.get('recibido'),fallback)))
    user_digest, users = sources['usuarios.db']
    for r in users.get('usuarios',[]):
        role={'admin':'ADMIN','tecnico':'TECNICO','operador':'OPERADOR'}.get(r['rol'])
        if not role: raise ValueError('Unknown legacy user role')
        insert('users',dict(email=r['correo'],name=r.get('nombre') or '',role=role,password_hash=None,active=bool(r['activo']),reset_required=True,created_at=timestamp(r.get('creado'),fallback)))
    for filename,(source_hash,tables) in sources.items():
        for table, records in tables.items():
            for record in records:
                clean={k:v for k,v in record.items() if k not in ('sal','clave')}
                insert('legacy_records',dict(source_sha256=source_hash,source_table=table,source_key=str(record['_source_rowid']),payload=encoded(clean)))
        insert('import_runs',dict(source_sha256=source_hash,counts=encoded({t:len(r) for t,r in tables.items()})))
    # Prove every source UID exists, not merely equality of global counts.
    for source,target in (('alarmas','alarms'),('logs','system_logs'),('muestras','telemetry_samples')):
        ids=[r['uid'] for r in data.get(source,[])]
        if ids:
            sql.append("SELECT 1 / CASE WHEN (SELECT count(*) FROM "+target+" WHERE uid IN ("+','.join(literal(i) for i in ids)+")) = "+str(len(ids))+" THEN 1 ELSE 0 END;")
    sql.append('COMMIT;')
    return '\n'.join(sql)+'\n', {name: {table:len(records) for table,records in tables.items()} for name,(_,tables) in sources.items()}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--backup',type=pathlib.Path,required=True)
    parser.add_argument('--container',required=True)
    parser.add_argument('--database',default='katana')
    parser.add_argument('--db-user',default='katana')
    args=parser.parse_args()
    sql, counts=plan(args.backup)
    subprocess.run(['docker','exec','-i',args.container,'psql','-X','-v','ON_ERROR_STOP=1','-U',args.db_user,'-d',args.database],input=sql.encode(),stdout=subprocess.DEVNULL,check=True)
    print(json.dumps({'verified_source_counts':counts,'passwords':'reset_required','target':args.database},indent=2))

if __name__=='__main__': main()
