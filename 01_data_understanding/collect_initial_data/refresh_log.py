"""Registro de actualizaciones de datos de cualquier fuente (BGG, Cazagangas, ...).

Una fila por corrida en `01_data_understanding/refresh_log.csv` (versionado, a
diferencia de `data/`). Es CSV y no .md para poder abrirlo como tabla (Numbers,
Excel, Google Sheets), filtrar por fuente y ordenar. Lo escriben los scripts,
no se edita a mano.

Columnas (las de filas se leen contra el total de la tabla, para saber si fue mucho o poco):
  fecha                día de la corrida
  fuente               de dónde salieron los datos ("BGG API", "Cazagangas ...")
  opciones             argumentos con que corrió
  filas_total          filas que tiene la tabla (el universo posible)
  filas_consultadas    cuántas se pidieron a la fuente en esta corrida
  pct_consultadas      filas_consultadas / filas_total
  filas_con_cambios    de las consultadas, cuántas quedaron con algún valor distinto
  pct_con_cambios      filas_con_cambios / filas_consultadas
  filas_nuevas         juegos que entraron al catálogo / links nuevos
  filas_no_devueltas   la fuente no devolvió nada (BGG: fusionado/borrado; Cazagangas: sin respuesta)
  columnas_total       columnas que se pueden actualizar
  columnas_consultadas cuántas se pidieron
  columnas_con_cambios cuántas tuvieron al menos un cambio
  columnas_detalle     cuáles, con su cantidad de cambios (columna:n;columna:n)
  celdas_cambiadas     total de valores (fila x columna) que cambiaron
  duracion_seg         duración de la corrida
  observacion          texto libre: por qué se corrió, qué quedó afuera y por qué (se pasa con --nota "...")
"""
import csv
import datetime
from pathlib import Path

LOG_PATH = Path(__file__).resolve().parents[1] / "refresh_log.csv"
COLUMNAS = [
    "fecha", "fuente", "opciones", "filas_total", "filas_consultadas", "pct_consultadas", "filas_con_cambios", "pct_con_cambios",
    "filas_nuevas", "filas_no_devueltas", "columnas_total", "columnas_consultadas", "columnas_con_cambios", "columnas_detalle",
    "celdas_cambiadas", "duracion_seg", "observacion",
]


def pct(parte, total):
    return f"{100 * parte / total:.1f}%" if total else ""


def write_refresh_log(fuente, opciones, filas_total, filas_consultadas, filas_con_cambios, filas_nuevas, filas_no_devueltas,
                      columnas_total, columnas_consultadas, columnas_cambiadas, duracion_seg, observacion=""):
    """`columnas_cambiadas`: dict columna -> cantidad de filas donde cambió (vacío si no cambió nada)."""
    cambiadas = columnas_cambiadas or {}
    fila = {
        "fecha": datetime.date.today().isoformat(),
        "fuente": fuente,
        "opciones": opciones,
        "filas_total": filas_total,
        "filas_consultadas": filas_consultadas,
        "pct_consultadas": pct(filas_consultadas, filas_total),
        "filas_con_cambios": filas_con_cambios,
        "pct_con_cambios": pct(filas_con_cambios, filas_consultadas),
        "filas_nuevas": filas_nuevas,
        "filas_no_devueltas": filas_no_devueltas,
        "columnas_total": columnas_total,
        "columnas_consultadas": columnas_consultadas,
        "columnas_con_cambios": len(cambiadas),
        "columnas_detalle": ";".join(f"{c}:{n}" for c, n in sorted(cambiadas.items(), key=lambda x: -x[1])),
        "celdas_cambiadas": sum(cambiadas.values()),
        "duracion_seg": int(duracion_seg),
        "observacion": observacion,
    }
    nuevo = not LOG_PATH.exists()
    with LOG_PATH.open("a", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNAS)
        if nuevo:
            w.writeheader()
        w.writerow(fila)
    return LOG_PATH
