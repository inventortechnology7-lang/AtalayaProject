#!/usr/bin/env python3
"""Generate local-only credentials without overwriting existing configuration."""
import os
import secrets
from pathlib import Path
path = Path(__file__).resolve().parents[1] / '.env'
values = dict(DB_PASSWORD=secrets.token_urlsafe(32), ADMIN_EMAIL='admin@katana.local',
              ADMIN_PASSWORD=secrets.token_urlsafe(32), PLACA_TOKEN=secrets.token_urlsafe(32))
fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
with os.fdopen(fd, 'w') as f:
    f.write(''.join(f'{k}={v}\n' for k,v in values.items()))
print('Created .env (0600). Credentials remain in that file.')
