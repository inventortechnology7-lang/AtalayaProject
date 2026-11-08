#!/usr/bin/env python3
"""Online, non-destructive legacy backup. Never prints credentials or deletes volumes."""
import datetime, hashlib, json, os, pathlib, sqlite3, subprocess
os.umask(0o077)
root = pathlib.Path('backups') / datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
root.mkdir(parents=True)
def run(*args):
    return subprocess.check_output(args)
manifest = {'source_revision': run('git','rev-parse','HEAD').decode().strip(), 'files': {}}
containers = json.loads(run('docker','inspect','atalaya-laptop-edge-1','atalaya-laptop-postgres-1'))
manifest['mounts'] = {c['Name']: c['Mounts'] for c in containers}
for name in ('katana.db','usuarios.db'):
    code = '''import sqlite3,sys,tempfile,pathlib
p=pathlib.Path('/data')/sys.argv[1]
if not p.exists(): raise SystemExit('Missing database: '+str(p))
src=sqlite3.connect('file:'+str(p)+'?mode=ro',uri=True)
with tempfile.TemporaryDirectory() as d:
 target=pathlib.Path(d)/'backup.db'
 dst=sqlite3.connect(target);src.backup(dst)
 assert dst.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
 dst.close();src.close();sys.stdout.buffer.write(target.read_bytes())
'''
    path=root/name
    path.write_bytes(run('docker','exec','atalaya-laptop-edge-1','python3','-c',code,name))
    with sqlite3.connect(f'file:{path}?mode=ro',uri=True) as db:
        assert db.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
        tables=[r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")]
        counts={t:db.execute('SELECT count(*) FROM "'+t.replace('"','""')+'"').fetchone()[0] for t in tables}
    manifest['files'][name]={'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'rows':counts,'integrity':'ok'}
path=root/'legacy-postgres.dump'
path.write_bytes(run('docker','exec','atalaya-laptop-postgres-1','pg_dump','-U','atalaya','-d','atalaya','-Fc'))
listing=subprocess.run(['docker','exec','-i','atalaya-laptop-postgres-1','pg_restore','--list'],input=path.read_bytes(),capture_output=True,check=True)
manifest['files'][path.name]={'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'archive_listing_verified':bool(listing.stdout)}
(root/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
print(root)
print(json.dumps(manifest['files'],indent=2))
