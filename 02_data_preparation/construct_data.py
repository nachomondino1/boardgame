"""Lee data/02_data_preparation/integrated_data.jsonl (salida de integrate_data.py: bgg_data.jsonl
(base) + bgg_collection.jsonl + cazagangas_data.jsonl
ya mergeados — correr ese script antes si alguna fuente cambió), calcula
las columnas derivadas y escribe docs/data/data.json, lo que consume el sitio.

integrated_data.jsonl es JSON Lines (un objeto por línea). Los campos de BGG
llegan CRUDOS, con los nombres de BGG (ver bgg_common.py): acá se construye
TODO lo que usa el sitio a partir de ellos — la columna de la web
(`anio`, `jug_min`, `puntaje_bgg`…) es siempre una derivación de un campo
crudo (`yearpublished`, `suggested_num_players`, `average`…).

puntaje_ajust_bgg y precio_calidad: ver sus docstrings más abajo (vivían
como fórmulas manuales en el Sheet original, se migraron leyendo la fórmula
real de la celda antes de sacar esas columnas de ahí). precio_calidad
depende de `costo`, que hoy no sale de ninguna fuente (Bosque Lúdico no
está integrado todavía) — da `None` para todos los juegos hasta que exista.

duracion y modo: derivadas 100% de datos de BGG (mecánicas, categorías,
duración mín./máx. — infer_modo, acá abajo).

`estado` y `mi_puntaje` salen de tu colección en BGG (bgg_collection.jsonl):
Own > Prev. owned > Want to buy, y "Watchlist" para todo lo demás.

`nombre` es el `name` de BGG; `grupo` se arma con las familias de BGG
(compute_grupos); `link_cazagangas` y `cazagangas_status` ya vienen resueltos
por integrate_data.py y pasan de largo.
"""
import collections
import json
import math
import re
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INTEGRATED_DATA_PATH = ROOT / "data" / "02_data_preparation" / "integrated_data.jsonl"
OUTPUT_PATH = ROOT / "docs" / "data" / "data.json"

# Grupos: juegos que son el mismo sistema con otra caja (mapa, expansión
# standalone, edición). Salen de las familias de BGG ("Game: Azul", "Series:
# Exit: The Game"): cada juego va a su familia más grande, y un grupo solo se
# acepta si al menos esa fracción de sus miembros comparte el principio del
# nombre ("Exit: …", "Azul: …") — así se descartan series de una editorial
# ("Series: Alea Big Box") que no son un mismo sistema de juego.
GRUPO_FAMILIAS = ("Game", "Series")
GRUPO_PREFIJO_COMUN_MIN = 0.6

PUBLISHER_IGNORADOS = ("(",)  # BGG lista "(Unknown)", "(Self-Published)", etc.

# Tags de BGG (mecánicas o categorías, da igual de cuál de las dos venga)
# que señalan modos de juego no competitivos de forma razonablemente
# confiable. "Semi-Cooperative Game" es el tag que usa BGG para juegos con
# un objetivo compartido pero intereses individuales en tensión (ej.
# traidor oculto) — el calce más cercano a "Cooperativo y competitivo".
MECANICA_SEMI_COOP = "Semi-Cooperative Game"
MECANICA_EQUIPOS = "Team-Based Game"
MECANICA_COOP = "Cooperative Game"

# Marketplace: precio de referencia = mediana de listados recientes en USD
# y en buen estado (ya filtrados por fecha en bgg_common.py).
MARKETPLACE_CONDICIONES = {"new", "likenew"}

PUNTAJE_AJUST_DESVIO = 1.4  # desvío estándar fijo histórico, ver docstring

# Campos de identidad que pasan de largo tal cual (strings; "" -> None).
PASSTHROUGH = ["bgg_id", "link_cazagangas"]


def num(value, zero_is_missing=False):
    """Número de un string crudo de BGG, o None. BGG usa 0 como "sin dato" en
    edad/duración/peso/puntaje (no es un valor real)."""
    try:
        n = float(value)
    except (TypeError, ValueError):
        return None
    return None if zero_is_missing and n == 0 else n


def to_int(n):
    return None if n is None else int(n)


def players_from_poll(suggested_num_players, poll_summary, box_min, box_max):
    """((best_min, best_max), (jug_min, jug_max)) a partir de los polls de
    cantidad de jugadores.
    - best: lo que dice el resumen de BGG ("Best with 3–4 players") si el
      juego lo tiene (lo trae la API); si no, la cantidad con más votos "Best".
    - rango de la comunidad: las cantidades donde Best + Recommended supera a
      Not Recommended — da lo mismo que el "Recommended with X–Y" de BGG
      (coincidió en 100 de 100 juegos).
    Sin votos, el rango cae al de la caja (minplayers/maxplayers)."""
    best_n, best_votes = None, 0
    recommended = set()
    for entry in suggested_num_players or []:
        votes = {r["@value"]: int(r["@numvotes"]) for r in entry.get("result", [])}
        label = entry.get("@numplayers", "")
        n = label.rstrip("+")
        if not n.isdigit():
            continue
        if votes.get("Best", 0) > best_votes:
            best_n, best_votes = int(n), votes["Best"]
        if not label.endswith("+") and votes.get("Best", 0) + votes.get("Recommended", 0) > votes.get("Not Recommended", 0):
            recommended.add(int(n))

    best = (best_n, best_n)
    for r in poll_summary or []:
        if r.get("@name") == "bestwith":
            nums = re.findall(r"\d+", r.get("@value", ""))
            if nums:
                best = (int(nums[0]), int(nums[-1]))
    rango = (min(recommended), max(recommended)) if recommended else (box_min, box_max)
    return best, rango


def top_vote(entries, key):
    """Valor de `key` de la opción más votada de un poll crudo, o None."""
    best, best_votes = None, 0
    for e in entries or []:
        votes = int(e.get("@numvotes", 0))
        if votes > best_votes:
            best, best_votes = e.get(key), votes
    return best


def dependencia_idioma(entries):
    """Nivel 1 (sin texto en el juego) a 5 (injugable en otro idioma) más
    votado. Se cuenta por posición: el `@level` del dataset de Hugging Face
    no siempre es confiable."""
    votes = [int(e.get("@numvotes", 0)) for e in entries or []]
    return votes.index(max(votes)) + 1 if votes and max(votes) > 0 else None


def marketplace_mediana_usd(listings):
    precios = []
    for l in listings or []:
        if l.get("currency") == "USD" and l.get("condition") in MARKETPLACE_CONDICIONES:
            p = num(l.get("price"))
            if p is not None:
                precios.append(p)
    return round(statistics.median(precios), 2) if precios else None


def infer_modo(mecanicas, categorias):
    """Devuelve un modo sugerido a partir de mecánicas/categorías de BGG,
    o None si no hay ninguna (no hay base para decidir, no hay que asumir
    "Competitivo" a ciegas)."""
    tags = set(mecanicas or []) | set(categorias or [])
    if not tags:
        return None
    if MECANICA_SEMI_COOP in tags:
        return "Cooperativo y competitivo"
    if MECANICA_EQUIPOS in tags:
        return "Equipos"
    if MECANICA_COOP in tags:
        return "Cooperativo"
    return "Competitivo"  # tenemos mecánicas/categorías y ninguna es de las de arriba


def estado_de(row):
    """Estado en tu colección de BGG: Own > Prev. owned > Want to buy; el
    resto (incluido no estar en la colección) es Watchlist."""
    if row.get("own") == "1":
        return "Own"
    if row.get("prevowned") == "1":
        return "Prev. owned"
    if row.get("wanttobuy") == "1":
        return "Want to buy"
    return "Watchlist"


def nombre_base(nombre):
    """Principio del nombre antes de ":", "–", "-" o "(", en minúscula."""
    return re.split(r"\s*[:–—-]\s|\s\(", nombre, maxsplit=1)[0].strip().lower()


def compute_grupos(rows):
    """{bgg_id: nombre del grupo} para los juegos que comparten familia de
    BGG con otros (ver GRUPO_FAMILIAS)."""
    def familias(row):
        return [f for f in row.get("boardgamefamily") or [] if f.split(":")[0] in GRUPO_FAMILIAS]

    tamanio = collections.Counter(f for row in rows for f in familias(row))
    miembros = collections.defaultdict(list)
    for row in rows:
        fs = familias(row)
        if fs:
            miembros[max(fs, key=lambda f: (tamanio[f], f))].append(row)

    grupos = {}
    for familia, juegos in miembros.items():
        if len(juegos) < 2:
            continue
        comun = collections.Counter(nombre_base(j.get("name") or "") for j in juegos).most_common(1)[0][1]
        if comun / len(juegos) >= GRUPO_PREFIJO_COMUN_MIN:
            nombre_grupo = re.sub(r"\s*\([^)]*\)$", "", familia.split(":", 1)[1].strip())  # sin "(Official)", "(Space Cowboys)"
            for j in juegos:
                grupos[j["bgg_id"]] = nombre_grupo
    return grupos


def build_game(row, grupo):
    """Una fila de integrated_data.jsonl (campos crudos de BGG) -> el juego
    que consume el sitio, con las columnas ya construidas."""
    game = {}
    for key in PASSTHROUGH:
        value = row.get(key)
        game[key] = (value.strip() if isinstance(value, str) else value) or None
    game["nombre"] = (row.get("name") or "").strip()
    game["bgg_url"] = f"https://boardgamegeek.com/boardgame/{game['bgg_id']}"
    game["estado"] = estado_de(row)
    rating = num(row.get("rating"))  # "N/A" si no puntuaste
    game["mi_puntaje"] = None if rating is None else (int(rating) if rating == int(rating) else rating)

    box_min = to_int(num(row.get("minplayers"), zero_is_missing=True))
    box_max = to_int(num(row.get("maxplayers"), zero_is_missing=True))
    (best_min, best_max), (jug_min, jug_max) = players_from_poll(
        row.get("suggested_num_players"), row.get("poll_summary"), box_min, box_max)
    rank = (row.get("Board Game Rank") or "").strip()
    publishers = [p for p in row.get("boardgamepublisher") or [] if not p.startswith(PUBLISHER_IGNORADOS)]
    designers = row.get("boardgamedesigner") or []
    edad_comunidad = top_vote(row.get("suggested_playerage"), "@value")

    game.update({
        "anio": to_int(num(row.get("yearpublished"))),
        "edad_min": to_int(num(row.get("minage"), zero_is_missing=True)),
        "jug_min": jug_min,
        "jug_max": jug_max,
        "jug_best_min": best_min,
        "jug_best_max": best_max,
        "duracion_min": to_int(num(row.get("minplaytime"), zero_is_missing=True)),
        "duracion_max": to_int(num(row.get("maxplaytime"), zero_is_missing=True)),
        "complejidad": num(row.get("averageweight"), zero_is_missing=True),
        "puntaje_bgg": num(row.get("average"), zero_is_missing=True),
        "reviews_bgg": to_int(num(row.get("usersrated"))),
        "ranking_bgg": int(rank) if rank.isdigit() else None,
        "disenador": ", ".join(designers) or None,
        "mecanicas": row.get("boardgamemechanic") or [],
        "categorias": row.get("boardgamecategory") or [],
        "imagen": (row.get("thumbnail") or "").strip() or None,
        "grupo": grupo,
        "cazagangas_status": row.get("cazagangas_status"),
        "publisher_principal": publishers[0] if publishers else None,
        "dependencia_idioma": dependencia_idioma(row.get("suggested_language_dependence")),
        "edad_comunidad": to_int(num(re.sub(r"\D.*", "", edad_comunidad))) if edad_comunidad else None,
        "precio_ref_usd": marketplace_mediana_usd(row.get("marketplacelistings")),
    })
    return game


def load_games():
    if not INTEGRATED_DATA_PATH.exists():
        raise SystemExit(f"No existe {INTEGRATED_DATA_PATH}; corré 02_data_preparation/integrate_data.py primero.")
    with INTEGRATED_DATA_PATH.open(encoding="utf-8") as f:
        rows = [json.loads(line) for line in f if line.strip()]
    if not rows:
        raise SystemExit(f"{INTEGRATED_DATA_PATH} está vacío; corré 02_data_preparation/integrate_data.py primero.")
    grupos = compute_grupos(rows)
    return [build_game(row, grupos.get(row["bgg_id"])) for row in rows]


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


def compute_modo(game):
    """Deriva `modo` de las mecánicas/categorías de BGG (infer_modo). Sin mecánicas/categorías en el caché (juego no
    enriquecido todavía, o BGG no las trae), infer_modo devuelve None en
    vez de asumir "Competitivo" a ciegas."""
    return infer_modo(game.get("mecanicas"), game.get("categorias"))


def build_games():
    """Todas las columnas derivadas, para todos los juegos de integrated_data.jsonl."""
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
    return games


def main():
    games = build_games()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(games, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"OK: {len(games)} juegos escritos en {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
