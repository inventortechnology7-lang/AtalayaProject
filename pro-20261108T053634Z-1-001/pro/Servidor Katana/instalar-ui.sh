#!/bin/bash
# Instala la interfaz web local como servicio de usuario (arranca al iniciar sesión).
set -e
mkdir -p ~/.config/systemd/user
cat > ~/.config/systemd/user/katana-ui.service <<'U'
[Unit]
Description=Katana - interfaz web local (puerto 8080)

[Service]
ExecStart=/usr/bin/python3 -I /home/alexis/katana-servidor/ui.py
WorkingDirectory=/home/alexis/katana-servidor
Restart=always
RestartSec=3

[Install]
WantedBy=default.target
U
systemctl --user daemon-reload
systemctl --user enable --now katana-ui.service
sudo loginctl enable-linger "$USER"   # arrancar sin iniciar sesión
sleep 1; systemctl --user is-active katana-ui; ss -ltn | grep ':8080'
