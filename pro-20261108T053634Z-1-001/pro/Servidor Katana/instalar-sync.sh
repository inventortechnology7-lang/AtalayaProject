#!/bin/bash
set -e
mkdir -p ~/.config/systemd/user
cat > ~/.config/systemd/user/katana-sync.service <<'U'
[Unit]
Description=Katana - sincronización hacia Negra

[Service]
ExecStart=/usr/bin/python3 -I /home/alexis/katana-servidor/sync.py
WorkingDirectory=/home/alexis/katana-servidor
Restart=always
RestartSec=5

[Install]
WantedBy=default.target
U
systemctl --user daemon-reload
systemctl --user enable --now katana-sync.service
sleep 1; systemctl --user is-active katana-sync
