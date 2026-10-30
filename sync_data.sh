#!/bin/bash
# Lo corres cuando actualizaste los datos de entrada (tu colección en BGG, bgg_data u otro) y queres reflejarlos en la web.

# Regenera el catálogo del sitio (docs/data/names.json, index.json y games/NNN.json) y lo
# commitea y pushea a staging, donde se prueba (GitHub Pages). Ver DATA_PLAYBOOK.md, "Gitignorear
# toda la fuente cruda" en Decisiones clave: el sync automático en CI ya no es posible porque
# data/01_data_understanding/ es gitignored, solo vive en esta máquina.
#
# No toca mvp (producción, Cloudflare): promover es a mano, ver "Ramas y despliegue" en MVP.md.
#
# Uso: ./sync_data.sh                    (tu colección + los 5000 mejor rankeados + juegos nuevos del hot, ~30 min)
#      ./sync_data.sh --scope all         (todo el catálogo, ~2 h; cualquier argumento va tal cual a refresh_bgg_data.py)
set -euo pipefail
cd "$(dirname "$0")"

if [ "$(git branch --show-current)" != "staging" ]; then
  echo "Este script commitea en staging y ahora estás en '$(git branch --show-current)'. Cambiá de rama y volvé a correrlo." >&2
  exit 1
fi

echo "== Actualizando los datos de BGG =="
if [ "$#" -eq 0 ]; then
  set -- --top 5000 --discover
fi
python3 01_data_understanding/collect_initial_data/bgg/refresh_bgg_data.py "$@"

echo "== Integrando fuentes =="
python3 02_data_preparation/integrate_data.py

echo "== Generando el catálogo del sitio =="
python3 02_data_preparation/build_catalog.py

git add docs/data/names.json docs/data/index.json docs/data/meta.json docs/data/games
if git diff --cached --quiet; then
  echo "== Sin cambios en el catálogo, nada que mandar =="
  exit 0
fi

echo "== Commiteando y pusheando a staging =="
git commit -m "Sync catálogo"
git push origin staging

echo "== Listo en staging: https://nachomondino1.github.io/boardgame/ =="
echo "== Para llevarlo a producción (mvp): ver 'Ramas y despliegue' en MVP.md =="
