"""Registro de actualizaciones de datos de cualquier fuente (BGG, Cazagangas, ...).

Una fila por corrida en `01_data_understanding/refresh_log.csv` (versionado, a
diferencia de `data/`). Es CSV y no .md para poder abrirlo como tabla (Numbers,
Excel, Google Sheets), filtrar por fuente y ordenar. Lo escriben los scripts,
no se edita a mano.

Columnas:
  fecha                día de la corrida
  fuente               de dónde salieron los datos ("BGG API", "Cazagangas")
  opciones             argumentos con que corrió
  filas_consultadas    juegos (filas) que se pidieron a la fuente
  filas_con_cambios    de esas, cuántas quedaron con algún valor distinto
  filas_nuevas         juegos que entraron al catálogo / links nuevos
  filas_no_devueltas   la fuente no devolvió nada (BGG: fusionado/borrado; Cazagangas: sin respuesta)
  columnas_con_cambios cuántas columnas distintas tuvieron al menos un cambio
  columnas_detalle     cuáles, con su cantidad de cambios (columna:n;columna:n)
  celdas_cambiadas     total de valores (fila x columna) que cambiaron
  duracion_seg         duración de la corrida
"""
import csv
import datetime
from pathlib import Path

LOG_PATH = Path(__file__).resolve().parents[1] / "refresh_log.csv"
COLUMNAS = [
    "fecha", "fuente", "opciones", "filas_consultadas", "filas_con_cambios", "filas_nuevas", "filas_no_devueltas",
    "columnas_con_cambios", "columnas_detalle", "celdas_cambiadas", "duracion_seg",
]


def write_refresh_log(fuente, script, opciones="", filas_consultadas=0, filas_con_cambios=0, filas_nuevas=0,
                      filas_no_devueltas=0, columnas_consultadas=None, columnas_cambiadas=None, duracion_seg=0, nota=""):
    """`columnas_cambiadas`: dict columna -> cantidad de filas donde cambió (vacío/None si no aplica)."""
    cambiadas = columnas_cambiadas or {}
    ahora = datetime.datetime.now()
    fila = {
        "fecha": ahora.date().isoformat(),
        "fuente": fuente,
        "opciones": opciones,
        "filas_consultadas": filas_consultadas,
        "filas_con_cambios": filas_con_cambios,
        "filas_nuevas": filas_nuevas,
        "filas_no_devueltas": filas_no_devueltas,
        "columnas_con_cambios": len(cambiadas),
        "columnas_detalle": ";".join(f"{c}:{n}" for c, n in sorted(cambiadas.items(), key=lambda x: -x[1])),
        "celdas_cambiadas": sum(cambiadas.values()),
        "duracion_seg": int(duracion_seg),
    }
    nuevo = not LOG_PATH.exists()
    with LOG_PATH.open("a", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNAS)
        if nuevo:
            w.writeheader()
        w.writerow(fila)
    return LOG_PATH
