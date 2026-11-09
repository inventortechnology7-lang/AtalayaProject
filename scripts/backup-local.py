#!/usr/bin/env python3
"""Consistent Katana PostgreSQL backup, SHA256 manifest; no volume changes."""
import argparse, datetime, hashlib, json, os, pathlib, subprocess
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--container', default='katana-local-katana-db-1')
args=parser.parse_args()
os.umask(0o077)
root=pathlib.Path('backups')/('local-'+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
root.mkdir(parents=True)
dump=subprocess.check_output(['docker','exec',args.container,'pg_dump','-U','katana','-d','katana','-Fc'])
subprocess.run(['docker','exec','-i',args.container,'pg_restore','--list'],input=dump,stdout=subprocess.DEVNULL,check=True)
(root/'katana.dump').write_bytes(dump)
(root/'manifest.json').write_text(json.dumps({'sha256':hashlib.sha256(dump).hexdigest(),'bytes':len(dump),'container':args.container},indent=2)+'\n')
print(root)
