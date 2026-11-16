#!/bin/bash
# Lleva a producción (rama mvp, Cloudflare) los datos recién generados en staging.
#
# Solo promueve cuando lo único que cambió en lo que se publica (docs/, functions/, src/,
# wrangler.jsonc, package.json) respecto de mvp son los datos (docs/data/). Si staging tiene
# cambios del sitio sin promover, no hace nada: eso se promueve a mano (ver MVP.md, sección 11).
# Después del push espera el deploy y chequea que el sitio y la función de la colección anden.
#
# Lo llama sync_data.sh al final. También se puede correr solo:
#   ./scripts/promote_data.sh              promueve (si las guardas lo permiten)
#   ./scripts/promote_data.sh --dry-run    muestra qué haría, sin pushear
#   ./scripts/promote_data.sh --check      solo chequea producción
set -euo pipefail
cd "$(dirname "$0")/.."

PROD_URL="https://boardgame-mvp.nachomondino1.workers.dev"
MODE="${1:-}"
MIN_RATIO=95  # el catálogo nuevo no puede tener menos del 95% de los juegos del que está en producción

aviso() {
  echo "!! $1" >&2
  osascript -e "display notification \"$1\" with title \"Juegos de mesa: sync\"" >/dev/null 2>&1 || true
}

meta_field() {  # lee un campo de un meta.json por stdin; vacío si no hay JSON (ej. todavía no existe en mvp)
  python3 -c "
import json, sys
try:
    print(json.load(sys.stdin).get('$1') or '')
except ValueError:
    print('')
"
}

# Chequea producción: la función de la colección responde 404 para un usuario inexistente.
# Un 500 es que el Worker perdió BGG_TOKEN (pasó una vez tras un deploy).
check_prod() {
  local esperada="${1:-}"
  if [ -n "$esperada" ]; then
    local visto=""
    for _ in 1 2 3 4 5 6 7 8 9 10; do
      visto=$(curl -fsS --max-time 20 "$PROD_URL/data/meta.json" 2>/dev/null | meta_field actualizado || true)
      [ "$visto" = "$esperada" ] && break
      sleep 30
    done
    if [ "$visto" != "$esperada" ]; then
      aviso "Producción todavía no muestra los datos del $esperada (vio '${visto:-nada}'). Revisá el deploy en Cloudflare."
      return 1
    fi
    echo "   producción ya sirve los datos del $esperada"
  fi
  local codigo
  codigo=$(curl -s -o /dev/null -w '%{http_code}' --max-time 30 "$PROD_URL/api/collection?user=zz_chequeo_no_existe_9" || echo "000")
  case "$codigo" in
    404) echo "   la función de la colección responde bien (404 para un usuario inexistente)" ;;
    500) aviso "La función /api/collection devuelve 500: falta BGG_TOKEN en el Worker. Cargalo en Cloudflare (Settings → Runtime → Variables and secrets)."; return 1 ;;
    *)   aviso "La función /api/collection respondió $codigo (se esperaba 404)."; return 1 ;;
  esac
}

if [ "$MODE" = "--check" ]; then
  check_prod
  exit $?
fi

git fetch -q origin mvp

# 1. ¿Hay cambios del sitio (que no sean datos) sin promover?
codigo=$(git diff --name-only origin/mvp staging -- docs functions src wrangler.jsonc package.json ':!docs/data' | head -5)
if [ -n "$codigo" ]; then
  echo "== No promuevo solo: staging tiene cambios del sitio sin promover =="
  echo "$codigo" | sed 's/^/   /'
  echo "   Promové a mano cuando estén listos (MVP.md, sección 11)."
  exit 0
fi

# 2. ¿El catálogo nuevo se ve sano?
nuevo=$(meta_field juegos_total < docs/data/meta.json)
previo=$(git show origin/mvp:docs/data/meta.json 2>/dev/null | meta_field juegos_total || true)
fecha=$(meta_field actualizado < docs/data/meta.json)
if [ -n "$previo" ] && [ "$nuevo" -lt $(( previo * MIN_RATIO / 100 )) ]; then
  aviso "El catálogo nuevo tiene $nuevo juegos y producción $previo: no promuevo (¿falló la actualización?)."
  exit 1
fi

if [ "$(git rev-parse origin/mvp)" = "$(git rev-parse staging)" ]; then
  echo "== Producción ya está al día con staging =="
  exit 0
fi

if [ "$MODE" = "--dry-run" ]; then
  echo "== (dry-run) Promovería staging a mvp: $(git rev-list --count origin/mvp..staging) commit(s), catálogo de $nuevo juegos (antes: ${previo:-?}), datos del $fecha =="
  exit 0
fi

echo "== Promoviendo staging a producción (mvp) =="
# Sin '+': si mvp tiene commits que staging no tiene, git lo rechaza en vez de pisarlo.
if ! git push origin staging:mvp; then
  aviso "No pude promover: mvp tiene cambios que staging no tiene. Resolvelo a mano (MVP.md, sección 11)."
  exit 1
fi

echo "== Chequeando producción (el deploy tarda un par de minutos) =="
check_prod "$fecha"
