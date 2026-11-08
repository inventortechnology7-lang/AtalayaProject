#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
probe=$(mktemp -d)
trap 'rm -rf "$probe"' EXIT
mkdir "$probe/protocol_probe"
cp firmware/protocol_probe/protocol_probe.ino "$probe/protocol_probe/"
cp firmware/protocol_probe/secrets.example.h "$probe/protocol_probe/secrets.h"
"${ARDUINO_CLI:-arduino-cli}" compile --fqbn arduino:renesas_uno:unor4wifi "$probe/protocol_probe"
"${ARDUINO_CLI:-arduino-cli}" compile --fqbn esp32:esp32:esp32 "$probe/protocol_probe"
