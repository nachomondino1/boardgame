"""Lee data/02_data_preparation/integrated_data.jsonl (salida de integrate_data.py: mis_datos.jsonl
+ bgg_data.jsonl + grupos.json + cazagangas_data.jsonl ya mergeados — correr
ese script antes si alguna fuente cambió), calcula las columnas derivadas y
escribe docs/data/data.json, lo que consume el sitio.

integrated_data.jsonl es JSON Lines (un objeto por línea, ver el docstring
de collect_bgg_data.py sobre por qué JSONL y no CSV): mecanicas/categorias
ya llegan como array, el resto de los campos como string u null.

puntaje_ajust_bgg y precio_calidad: ver sus docstrings más abajo (vivían
como fórmulas manuales en el Sheet original, se migraron leyendo la fórmula
real de la celda antes de sacar esas columnas de ahí). precio_calidad
depende de `costo`, que hoy no sale de ninguna fuente (Bosque Lúdico no
está integrado todavía) — da `None` para todos los juegos hasta que exista.

duracion y modo: derivadas de datos de BGG (mecánicas, categorías,
duración mín./máx.). `modo` nunca pisa un valor que ya esté cargado a mano
en mis_datos.jsonl (columna propia, ver collect_bgg_data.py).

`transportable` es 100% manual (columna propia, ver collect_bgg_data.py):
BGG no trackea tamaño de caja en ningún campo, así que acá no se deriva de
nada, solo pasa de largo el valor que ya viene en mis_datos.jsonl.

`grupo`, `link_cazagangas`, `cazagangas_status` ya vienen resueltos por
integrate_data.py — acá solo pasan de largo (igual que `transportable`),
no se recalculan.
"""
import json
import math
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INTEGRATED_DATA_PATH = ROOT / "data" / "02_data_preparation" / "integrated_data.jsonl"
OUTPUT_PATH = ROOT / "docs" / "data" / "data.json"

PUNTAJE_AJUST_DESVIO = 1.4  # desvío estándar fijo histórico, ver docstring

NUMERIC_FLOAT = {"complejidad", "puntaje_bgg"}
NUMERIC_INT = {"anio", "edad_min", "jug_min", "jug_max", "jug_best_min", "jug_best_max",
               "duracion_min", "duracion_max", "reviews_bgg", "ranking_bgg", "mi_puntaje"}
LIST_FIELDS = {"mecanicas", "categorias"}


def load_games():
    if not INTEGRATED_DATA_PATH.exists():
        raise SystemExit(f"No existe {INTEGRATED_DATA_PATH}; corré 02_data_preparation/integrate_data.py primero.")
    with INTEGRATED_DATA_PATH.open(encoding="utf-8") as f:
        rows = [json.loads(line) for line in f if line.strip()]
    if not rows:
        raise SystemExit(f"{INTEGRATED_DATA_PATH} está vacío; corré 02_data_preparation/integrate_data.py primero.")

    games = []
    for row in rows:
        game = {}
        for key, value in row.items():
            if key in LIST_FIELDS:
                game[key] = value if isinstance(value, list) else []
                continue
            value = (value or "").strip()
            if not value:
                game[key] = None
            elif key in NUMERIC_FLOAT:
                game[key] = float(value)
            elif key in NUMERIC_INT:
                game[key] = int(float(value))
            else:
                game[key] = value
        games.append(game)
    return games


def compute_puntaje_ajust_bgg(game):
    """Ajusta puntaje_bgg hacia abajo cuando tiene pocas reviews (un juego
    con puntaje alto pero pocas reviews es menos confiable que uno con el
    mismo puntaje y muchas): puntaje_bgg - 3 * 1.4 / sqrt(reviews_bgg). El
    1.4 es una desviación estándar fija (no la del dataset actual, que
    varía con cada sync): es la que estaba hardcodeada en la fórmula
    original del Sheet en la gran mayoría de las filas, elegida como la
    oficial sobre una variante minoritaria que sí recalculaba el desvío en
    vivo, para que el ajuste no cambie de una corrida a otra solo porque
    cambió el desvío del catálogo."""
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
    """Promedio de dos z-scores — costo invertido (más barato = mejor) y
    puntaje_ajust_bgg (más puntaje = mejor) — cada uno respecto a la
    media/desvío del catálogo actual: promedio(-zscore(costo),
    zscore(puntaje_ajust_bgg)). Depende de puntaje_ajust_bgg, por eso se
    calcula después."""
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


def compute_duracion(game):
    """Un solo número de duración (minutos) a partir de duracion_min/
    duracion_max de BGG: el promedio de ambos cuando los dos están, el que
    haya si falta uno, o lo que ya hubiera en `duracion` como último
    recurso (no debería pasar: BGG siempre los trae juntos o ninguno)."""
    mn, mx = game.get("duracion_min"), game.get("duracion_max")
    if mn is not None and mx is not None:
        return round((mn + mx) / 2)
    if mx is not None:
        return mx
    if mn is not None:
        return mn
    return game.get("duracion")


# Tags de BGG (mecánicas o categorías, da igual de cuál de las dos venga)
# que señalan modos de juego no competitivos de forma razonablemente
# confiable. "Semi-Cooperative Game" es el tag que usa BGG para juegos con
# un objetivo compartido pero intereses individuales en tensión (ej.
# traidor oculto) — el calce más cercano a "Cooperativo y competitivo".
MECANICA_SEMI_COOP = "Semi-Cooperative Game"
MECANICA_EQUIPOS = "Team-Based Game"
MECANICA_COOP = "Cooperative Game"


def compute_modo(game):
    """Deriva `modo` de las mecánicas/categorías de BGG cuando no está ya
    cargado a mano (mi_ludoteca.json manda). Sin mecánicas/categorías en el
    caché (juego no enriquecido todavía, o BGG no las trae), no hay base
    para decidir: queda en None en vez de asumir "Competitivo" a ciegas."""
    if game.get("modo"):
        return game["modo"]

    tags = set(game.get("mecanicas") or []) | set(game.get("categorias") or [])
    if not tags:
        return None
    if MECANICA_SEMI_COOP in tags:
        return "Cooperativo y competitivo"
    if MECANICA_EQUIPOS in tags:
        return "Equipos"
    if MECANICA_COOP in tags:
        return "Cooperativo"
    return "Competitivo"  # tenemos mecánicas/categorías y ninguna es de las de arriba


def main():
    games = load_games()

    for g in games:
        g["duracion"] = compute_duracion(g)
        g["modo"] = compute_modo(g)
        g["puntaje_ajust_bgg"] = compute_puntaje_ajust_bgg(g)
    compute_precio_calidad(games)  # usa puntaje_ajust_bgg sin redondear, como hacía el Sheet

    for g in games:
        if g["puntaje_ajust_bgg"] is not None:
            g["puntaje_ajust_bgg"] = round(g["puntaje_ajust_bgg"], 2)
        if g["precio_calidad"] is not None:
            g["precio_calidad"] = round(g["precio_calidad"], 2)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(games, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"OK: {len(games)} juegos escritos en {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
