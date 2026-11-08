#!/bin/bash
# Pide la clave de Negra (sin mostrarla) y la guarda en .env. No la pegues en el chat.
cd "$(dirname "$0")"
read -r -s -p "Clave del usuario katana-laspalmas@inventor.local: " CLAVE; echo
[ -n "$CLAVE" ] || { echo "Vacía, no se guardó nada."; exit 1; }
sed -i '/^NEGRA_URL=/d;/^SYNC_USUARIO=/d;/^SYNC_CLAVE=/d;/^CONDOMINIO_ID=/d' .env
printf 'NEGRA_URL=http://100.101.225.120\nSYNC_USUARIO=katana-laspalmas@inventor.local\nSYNC_CLAVE=%s\nCONDOMINIO_ID=1\n' "$CLAVE" >> .env
chmod 600 .env
echo "Guardado en .env."
