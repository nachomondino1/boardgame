#!/bin/bash
# Lo corres cuando actualizaste los datos de entrada (tu colección en BGG, bgg_data u otro) y queres reflejarlos en la web.

# Regenera el catálogo del sitio (docs/data/names.json, index.json y games/NNN.json) y lo
# commitea y pushea a staging, donde se prueba (GitHub Pages). Ver DATA_PLAYBOOK.md, "Gitignorear
# toda la fuente cruda" en Decisiones clave: el sync automático en CI ya no es posible porque
# data/01_data_understanding/ es gitignored, solo vive en esta máquina.
#
# Al final llama a scripts/promote_data.sh, que lleva los datos a producción (mvp, Cloudflare) solo si
# staging no tiene cambios del sitio sin promover; si los tiene, promover es a mano (MVP.md, sección 11).
#
# Uso: ./sync_data.sh                    (tu colección + los 5000 mejor rankeados + juegos nuevos del hot, ~30 min)
#      ./sync_data.sh --scope all         (todo el catálogo, ~2 h; cualquier argumento va tal cual a refresh_bgg_data.py)
#      ./sync_data.sh --mensual           (lo que corre solo el LaunchAgent, ~2,5-3 h: todo BGG con --discover, el resumen de
#                                          movimientos de ranking/reviews, links nuevos de Cazagangas y sus precios en pasada rápida)
set -euo pipefail
cd "$(dirname "$0")"
MENSUAL=0
if [ "${1:-}" = "--mensual" ]; then
  MENSUAL=1
  shift
  set -- --scope all --fields all --discover --motivo "Actualización mensual automática"
fi

if [ "$(git branch --show-current)" != "staging" ]; then
  echo "Este script commitea en staging y ahora estás en '$(git branch --show-current)'. Cambiá de rama y volvé a correrlo." >&2
  exit 1
fi

echo "== Actualizando los datos de BGG =="
if [ "$#" -eq 0 ]; then
  set -- --top 5000 --discover
fi
python3 01_data_understanding/collect_initial_data/bgg/refresh_bgg_data.py "$@"

# Los pasos de la corrida mensual no frenan el sync si fallan (Cazagangas es un sitio externo): el catálogo se
# regenera igual con lo que haya, y la falla queda a la vista en el log.
if [ "$MENSUAL" -eq 1 ]; then
  echo "== Resumen de movimientos de BGG (ranking y reviews contra la foto anterior) =="
  python3 01_data_understanding/collect_initial_data/bgg/resumen_actualizacion_bgg.py --nota "Actualización mensual completa" \
    || echo "!! El resumen de BGG no se generó (ver arriba). Si falta la foto: --base-git <commit> (docstring del script)."
  echo "== Cazagangas: links de juegos nuevos =="
  python3 01_data_understanding/collect_initial_data/cazagangas/load_cazagangas_sitemap.py \
    || echo "!! No se actualizaron los links de Cazagangas (ver arriba)."
  echo "== Cazagangas: precios (pasada rápida) =="
  python3 01_data_understanding/collect_initial_data/cazagangas/load_cazagangas_prices.py --rapido --motivo "Actualización mensual automática" \
    || echo "!! No se actualizaron los precios de Cazagangas (ver arriba)."
fi

echo "== Integrando fuentes =="
python3 02_data_preparation/integrate_data.py

echo "== Generando el catálogo del sitio =="
python3 02_data_preparation/build_catalog.py

git add docs/data/names.json docs/data/index.json docs/data/meta.json docs/data/games
# Los registros de actualización (versionados) viajan con el catálogo.
git add 01_data_understanding/logs_actualizacion_data.csv
[ -f 01_data_understanding/resumen_actualizaciones_bgg.csv ] && git add 01_data_understanding/resumen_actualizaciones_bgg.csv
if git diff --cached --quiet; then
  echo "== Sin cambios en el catálogo, nada que commitear =="
else
  echo "== Commiteando y pusheando a staging =="
  git commit -m "Sync catálogo"
  git push origin staging
  echo "== Listo en staging: https://nachomondino1.github.io/boardgame/ =="
fi

# Los datos también salen a producción, pero solo si staging no tiene cambios del sitio sin promover
# (ver scripts/promote_data.sh). Si esto falla, staging ya quedó actualizada: no es motivo para repetir el sync.
echo "== Promoviendo datos a producción (mvp) =="
./scripts/promote_data.sh || echo "!! La promoción no se completó (ver arriba). Staging quedó actualizada; producción se promueve a mano (MVP.md, sección 11)."
