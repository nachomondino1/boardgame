"""Registro de actualizaciones de datos de cualquier fuente (BGG, Cazagangas, ...).

Una fila por corrida en `01_data_understanding/refresh_log.csv` (versionado, a
diferencia de `data/`). Es CSV y no .md para abrirlo como tabla (Numbers, Excel,
Google Sheets) y poder filtrar por fuente. Lo escriben los scripts; no se edita a mano.

Pocas columnas, las que importan:
  fecha                día de la corrida
  fuente               de dónde salen los datos (BGG, Cazagangas)
  metodo               cómo se consulta esa fuente (API, sitemap, scraping de página, ...)
  motivo               por qué se corrió esta actualización (--motivo "...")
  filas_total          filas que tiene la tabla (el universo posible)
  filas_actualizadas   cuántas se actualizaron en esta corrida
  pct_actualizadas     filas_actualizadas / filas_total
  duracion             cuánto tardó la corrida
  control              chequeo de que la actualización anduvo: qué tanto cambiaron los datos
                       (si cambia todo, o nada, algo anduvo mal)
  observacion          cualquier otra cosa a anotar, p. ej. por qué no fueron todas las filas (--nota "...")
"""
import csv
import datetime
from pathlib import Path

LOG_PATH = Path(__file__).resolve().parents[1] / "refresh_log.csv"
COLUMNAS = ["fecha", "fuente", "metodo", "motivo", "filas_total", "filas_actualizadas", "pct_actualizadas", "duracion", "control", "observacion"]


def duracion_txt(segundos):
    h, resto = divmod(int(segundos), 3600)
    m, s = divmod(resto, 60)
    return (f"{h} h " if h else "") + (f"{m} min " if h or m else "") + f"{s} s"


def pct(parte, total):
    return f"{100 * parte / total:.1f}%" if total else ""


def write_refresh_log(fuente, metodo, filas_total, filas_actualizadas, segundos, control="", motivo="", observacion=""):
    fila = {
        "fecha": datetime.date.today().isoformat(),
        "fuente": fuente,
        "metodo": metodo,
        "motivo": motivo,
        "filas_total": filas_total,
        "filas_actualizadas": filas_actualizadas,
        "pct_actualizadas": pct(filas_actualizadas, filas_total),
        "duracion": duracion_txt(segundos),
        "control": control,
        "observacion": observacion,
    }
    nuevo = not LOG_PATH.exists()
    with LOG_PATH.open("a", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNAS)
        if nuevo:
            w.writeheader()
        w.writerow(fila)
    return LOG_PATH
