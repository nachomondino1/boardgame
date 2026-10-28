#!/bin/bash
# Actualiza data.json a mano (ver DATA_PLAYBOOK.md, "Gitignorear toda la
# fuente cruda" en Decisiones clave: el sync automático en CI ya no es
# posible porque data/01_data_understanding/ es gitignored, solo vive en
# esta máquina) y lo manda a la web: corre el pipeline completo, commitea
# docs/data/data.json si cambió, pushea staging, abre un PR a main y lo
# mergea (GitHub Pages sirve directo de main:/docs).
#
# Uso: ./sync_data.sh
set -euo pipefail
cd "$(dirname "$0")"

echo "== Sumando juegos nuevos de universo_juegos.jsonl a bgg_data.jsonl =="
python3 01_data_understanding/collect_initial_data/search_new_game.py

echo "== Integrando fuentes =="
python3 02_data_preparation/integrate_data.py

echo "== Calculando columnas derivadas =="
python3 02_data_preparation/construct_data.py

echo "== Recortando Watchlist =="
python3 02_data_preparation/select_data.py

git add docs/data/data.json
if git diff --cached --quiet; then
  echo "== Sin cambios en docs/data/data.json, nada que mandar a la web =="
  exit 0
fi

echo "== Commiteando y pusheando a staging =="
git commit -m "Sync data.json"
git push origin staging

if [ -z "$(git log --oneline origin/main..staging)" ]; then
  echo "== staging ya está al día con main, nada que mergear =="
  exit 0
fi

echo "== Abriendo PR y mergeando a main =="
gh pr create --base main --head staging --title "Sync data.json" --body "Actualización de datos vía sync_data.sh." 2>/dev/null || true
gh pr merge staging --merge

echo "== Listo: https://nachomondino1.github.io/boardgame/ =="
