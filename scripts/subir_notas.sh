#!/bin/bash
# Sube tus notas (docs/data/notas.json, generado por build_catalog.py) al KV `NOTAS` de Cloudflare, de donde las lee
# functions/api/notas.js. Correr después de agregar notas con scripts/nota.py y regenerar el catálogo.
set -euo pipefail
cd "$(dirname "$0")/.."
python3 02_data_preparation/build_catalog.py >/dev/null
npx --yes wrangler kv key put notas --path docs/data/notas.json --binding NOTAS --remote
