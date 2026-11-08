#!/bin/bash
# Instala y arranca katana-receptor; abre 8300 solo para la LAN si ufw está activo.
set -e
[ "$EUID" -eq 0 ] || { echo "Ejecuta con sudo: sudo bash $0"; exit 1; }
install -m 644 /home/alexis/katana-servidor/katana-receptor.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now katana-receptor.service
if command -v ufw >/dev/null && ufw status | grep -q "Status: active"; then
  ufw allow from 192.168.100.0/24 to any port 8300 proto tcp comment 'Katana nodos LAN'
else
  echo "ufw no está activo: no se tocó el firewall."
fi
sleep 1; systemctl --no-pager status katana-receptor.service | head -8
ss -ltn | grep ':8300'
