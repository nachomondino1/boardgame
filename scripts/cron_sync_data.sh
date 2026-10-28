#!/bin/bash
# Wrapper para el LaunchAgent (~/Library/LaunchAgents/com.nachomondino.boardgame-sync.plist):
# corre sync_data.sh una vez por mes, pero no depende de que la Mac esté
# prendida justo el día 1 — launchd dispara este script en el horario
# programado Y en cada login/wake (RunAtLoad), y acá se chequea si ya pasó
# ~1 mes desde la última corrida real antes de hacer algo. Así, si la Mac
# estuvo apagada el día 1, la corrida pendiente sale apenas la prendés de
# nuevo, en vez de perderse en silencio hasta el mes siguiente.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# ~/cronjobs/<job>/: carpeta dedicada para todo lo de cronjobs locales en
# esta máquina (binario compilado, estado, log) — separado del repo
# porque son artefactos de esta Mac puntual, no del proyecto.
STATE_DIR="$HOME/cronjobs/boardgame-sync"
STATE_FILE="$STATE_DIR/last_run"
LOG_FILE="$STATE_DIR/sync.log"
MIN_DAYS_BETWEEN_RUNS=25

mkdir -p "$STATE_DIR"

now_epoch=$(date +%s)
if [ -f "$STATE_FILE" ]; then
  last_epoch=$(cat "$STATE_FILE")
  days_since=$(( (now_epoch - last_epoch) / 86400 ))
  if [ "$days_since" -lt "$MIN_DAYS_BETWEEN_RUNS" ]; then
    echo "$(date '+%Y-%m-%d %H:%M:%S') skip: corrió hace $days_since día(s), todavía no toca." >> "$LOG_FILE"
    exit 0
  fi
fi

echo "$(date '+%Y-%m-%d %H:%M:%S') == corriendo sync_data.sh ==" >> "$LOG_FILE"
cd "$REPO_DIR"
# PATH explícito: launchd no hereda el shell interactivo (sin Homebrew en PATH por default)
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
if ./sync_data.sh >> "$LOG_FILE" 2>&1; then
  echo "$now_epoch" > "$STATE_FILE"
  echo "$(date '+%Y-%m-%d %H:%M:%S') == listo ==" >> "$LOG_FILE"
else
  echo "$(date '+%Y-%m-%d %H:%M:%S') == FALLÓ, ver log arriba — no se actualiza last_run, reintenta en el próximo disparo ==" >> "$LOG_FILE"
fi
