"""Calcula columnas derivadas que no vienen de ninguna fuente (Sheet, BGG,
Bosque Lúdico) sino que se construyen a partir de otras columnas ya
integradas. Corre después de integrate_data.py, sobre docs/data/data.json.

Hasta ahora estas dos columnas vivían en el Sheet como fórmulas manuales;
se sacaron de ahí (el Sheet solo deja datos que no sean de BGG ni de Bosque
Lúdico) y se migraron acá. Las fórmulas se leyeron directo de las celdas del
Sheet antes de borrarlas, no se reinventaron:

puntaje_ajust_bgg: ajusta puntaje_bgg hacia abajo cuando tiene pocas reviews
(un juego con puntaje alto pero pocas reviews es menos confiable que uno con
el mismo puntaje y muchas):
    puntaje_bgg - 3 * 1.4 / sqrt(reviews_bgg)
El 1.4 es una desviación estándar fija (no la del dataset actual, que varía
con cada sync): es la que estaba hardcodeada en la fórmula original del
Sheet en la gran mayoría de las filas, elegida como la oficial sobre una
variante minoritaria que sí recalculaba el desvío en vivo, para que el
ajuste no cambie de una corrida a otra solo porque cambió el desvío del
catálogo.

precio_calidad ("Relación precio/calidad"): promedio de dos z-scores —
costo invertido (más barato = mejor) y puntaje_ajust_bgg (más puntaje =
mejor) — cada uno respecto a la media/desvío del catálogo actual:
    promedio( -zscore(costo), zscore(puntaje_ajust_bgg) )
Depende de puntaje_ajust_bgg, por eso se calcula después.
"""
import json
import math
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_PATH = ROOT / "docs" / "data" / "data.json"

PUNTAJE_AJUST_DESVIO = 1.4  # desvío estándar fijo histórico, ver docstring


def compute_puntaje_ajust_bgg(game):
    puntaje = game.get("puntaje_bgg")
    reviews = game.get("reviews_bgg")
    if puntaje is None or not reviews:
        return None
    return puntaje - 3 * PUNTAJE_AJUST_DESVIO / math.sqrt(reviews)


def zscore(value, mean, stdev):
    if value is None or not stdev:
        return None
    return (value - mean) / stdev


def compute_precio_calidad(games):
    costos = [g["costo"] for g in games if g.get("costo") is not None]
    ajustados = [g["puntaje_ajust_bgg"] for g in games if g.get("puntaje_ajust_bgg") is not None]
    if len(costos) < 2 or len(ajustados) < 2:
        for g in games:
            g["precio_calidad"] = None
        return  # no hay suficientes datos para un desvío estándar con sentido

    costo_mean, costo_stdev = statistics.mean(costos), statistics.stdev(costos)
    ajust_mean, ajust_stdev = statistics.mean(ajustados), statistics.stdev(ajustados)

    for g in games:
        z_costo = zscore(g.get("costo"), costo_mean, costo_stdev)
        z_ajust = zscore(g.get("puntaje_ajust_bgg"), ajust_mean, ajust_stdev)
        g["precio_calidad"] = (-z_costo + z_ajust) / 2 if z_costo is not None and z_ajust is not None else None


def main():
    games = json.loads(DATA_PATH.read_text(encoding="utf-8"))

    for g in games:
        g["puntaje_ajust_bgg"] = compute_puntaje_ajust_bgg(g)
    compute_precio_calidad(games)  # usa puntaje_ajust_bgg sin redondear, como hacía el Sheet

    for g in games:
        if g["puntaje_ajust_bgg"] is not None:
            g["puntaje_ajust_bgg"] = round(g["puntaje_ajust_bgg"], 2)
        if g["precio_calidad"] is not None:
            g["precio_calidad"] = round(g["precio_calidad"], 2)

    DATA_PATH.write_text(json.dumps(games, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"OK: puntaje_ajust_bgg y precio_calidad calculados para {len(games)} juegos en {DATA_PATH}")


if __name__ == "__main__":
    main()
