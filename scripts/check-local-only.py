#!/usr/bin/env python3
"""Check the tracked final tree, without printing credentials or scanning private backups."""
import pathlib, re, subprocess
paths=subprocess.check_output(['git','ls-files','-z']).decode().split('\0')
errors=[]
for name in filter(None,paths):
    p=pathlib.Path(name)
    if not p.is_file(): continue
    if name.endswith(('.env','secrets.h')) or '/atalaya/' in name or name.startswith('edge/'):
        errors.append(name+': obsolete source or credential file')
    try: text=p.read_text()
    except UnicodeError: continue
    if re.search(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|gh[pousr]_[A-Za-z0-9]{30,}|AKIA[0-9A-Z]{16}',text):
        errors.append(name+': credential pattern')
    if name.startswith(('backend/src/main/java/','web/src/','mobile/','compose')) and re.search(r'NEGRA_URL|SYNC_CLAVE|SYNC_USUARIO|/api/sync|expo-notifications',text):
        errors.append(name+': central dependency')
if errors: raise SystemExit('\n'.join(errors))
print('PASS: local-only tracked sources and credential-pattern scan (not a Git-history audit)')
