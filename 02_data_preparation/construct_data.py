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
Own > Prev. owned > Want to buy > Want to play, y "Watchlist" para todo lo demás.

`nombre` es el `name` de BGG; `grupo` se arma con las familias de BGG
(compute_grupos); `link_cazagangas` y `cazagangas_status` ya vienen resueltos
por integrate_data.py y pasan de largo.
"""
import collections
import datetime
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
GRUPO_MECANICAS_MIN = 0.3  # parecido (Jaccard) de mecánicas con el juego principal del grupo
GRUPO_COMPLEJIDAD_MAX = 1.0  # diferencia máxima de complejidad con el juego principal

PUBLISHER_IGNORADOS = ("(",)  # BGG lista "(Unknown)", "(Self-Published)", etc.

# Tags de BGG (mecánicas o categorías, da igual de cuál de las dos venga)
# que señalan modos de juego no competitivos de forma razonablemente
# confiable. "Semi-Cooperative Game" es el tag que usa BGG para juegos con
# un objetivo compartido pero intereses individuales en tensión (ej.
# traidor oculto) — el calce más cercano a "Cooperativo y competitivo".
MECANICA_SEMI_COOP = "Semi-Cooperative Game"
MECANICA_EQUIPOS = "Team-Based Game"
MECANICA_COOP = "Cooperative Game"

# Marketplace: precio de referencia = mediana de listados recientes (USD, EUR y GBP pasados a USD),
# solo de juegos NUEVOS (ya filtrados por fecha en bgg_common.py): los "como nuevo"
# son usados y bajan el precio, y el precio de Cazagangas también es solo de nuevos
# (comparar peras con peras). Con "new" y "likenew" eran 5.311 juegos con precio; solo "new", 3.618.
MARKETPLACE_CONDICIONES = {"new"}

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


PRECIO_SIN_STOCK_MAX_DIAS = 180  # un juego sin stock mantiene su último precio visto hasta 6 meses (decisión 2026-11-20)


def precio_cazagangas(row):
    """`precio_ars`: el más barato en tiendas de Cazagangas. Con stock hoy es ese precio; sin stock, el último que
    se vio, mientras no tenga más de PRECIO_SIN_STOCK_MAX_DIAS. `precio_ars_visto`: la fecha en que se vio ese
    último precio, solo si el juego está sin stock (null si el precio es de hoy): la web lo marca como "últ.".
    Sin precio visto nunca, o más viejo que el límite, queda sin precio real (la web cae a la estimación)."""
    precio = row.get("precio_cazagangas")
    if precio is None:
        return {"precio_ars": None, "precio_ars_visto": None}
    if row.get("tiendas_cazagangas"):
        return {"precio_ars": precio, "precio_ars_visto": None}
    visto = row.get("fecha_con_stock_cazagangas")
    try:
        dias = (datetime.date.today() - datetime.date.fromisoformat(visto)).days
    except (TypeError, ValueError):
        return {"precio_ars": None, "precio_ars_visto": None}
    if dias > PRECIO_SIN_STOCK_MAX_DIAS:
        return {"precio_ars": None, "precio_ars_visto": None}
    return {"precio_ars": precio, "precio_ars_visto": visto}


# Otras monedas del marketplace, llevadas a "USD equivalente de EE.UU." con un factor fijo. No es el tipo de cambio
# (EUR ~1,1 y GBP ~1,3): los avisos europeos son más caros que los de EE.UU. y con el cambio puro el multiplicador
# a pesos (PRECIO_MULT) bajaba de 2,1 a 1,5. Los factores 0,8 y 0,95 lo dejan en ~2 (medido el 2026-11-25 sobre los
# juegos con precio real de Cazagangas). Sumarlas duplica los juegos con referencia y evita que, con 1 o 2 avisos en
# USD, un solo disparate ($9 en Dune: Imperium – Uprising, que vale ~$60) fije el precio.
MARKETPLACE_A_USD = {"USD": 1.0, "EUR": 0.8, "GBP": 0.95}


PRECIO_MIN_USD = 5          # un juego nuevo por menos de esto es un error o un accesorio
PRECIO_RANGO_MAX = 2.0      # un aviso se descarta si es más de 2 veces mayor o menor que la mediana de los demás
PRECIO_AMBIGUO_MAX = 2.0    # con 2 avisos que difieren más de esto no hay forma de saber cuál es el disparate


def marketplace_mediana_usd(listings):
    """Precio de referencia en USD (equivalente EE.UU.) o None si no hay uno confiable.
    1) pasa los avisos a USD y descarta los absurdamente baratos;
    2) con 3 o más, descarta los outliers (fuera de mediana/2..mediana×2) y toma la mediana de los que quedan;
    3) con 2 avisos parecidos, su promedio; con 2 muy distintos no se sabe cuál es el disparate: None (sin dato
       es mejor que un precio equivocado: $9 de un aviso basura en Dune: Imperium – Uprising, 55 y 500 en
       Wondrous Creatures);
    4) con 1 aviso, ese."""
    precios = []
    for l in listings or []:
        tasa = MARKETPLACE_A_USD.get(l.get("currency"))
        if tasa and l.get("condition") in MARKETPLACE_CONDICIONES:
            p = num(l.get("price"))
            if p is not None and p * tasa >= PRECIO_MIN_USD:
                precios.append(p * tasa)
    if not precios:
        return None
    if len(precios) == 2:
        if max(precios) / min(precios) > PRECIO_AMBIGUO_MAX:
            return None
        return round(statistics.mean(precios), 2)
    if len(precios) >= 3:
        m = statistics.median(precios)
        precios = [p for p in precios if m / PRECIO_RANGO_MAX <= p <= m * PRECIO_RANGO_MAX]
        # (la mediana siempre sobrevive: queda al menos un aviso)
    return round(statistics.median(precios), 2)


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
    if row.get("wanttoplay") == "1":
        return "Want to play"
    return "Watchlist"


def nombre_base(nombre):
    """Principio del nombre antes de ":", "–", "-" o "(", en minúscula."""
    return re.split(r"\s*[:–—-]\s|\s\(", nombre, maxsplit=1)[0].strip().lower()


def compute_grupos(rows):
    """{bgg_id: nombre del grupo} para los juegos que comparten familia de
    BGG con otros (ver GRUPO_FAMILIAS)."""
    def familias(row):
        return [f for f in row.get("boardgamefamily") or [] if f.split(":")[0] in GRUPO_FAMILIAS]

    # Las versiones "Duel"/"Duet" (2 jugadores: "7 Wonders Duel", "Azul: Duel",
    # "Codenames: Duet") son otro juego que el original, no una variante: no se
    # agrupan con una familia de más jugadores. Sí con una familia que sea
    # mayormente de 2 jugadores (las expansiones del propio Duel).
    def es_duel(row):
        return str(row.get("maxplayers")) == "2" and re.search(r"\b(Duel|Duet|Duo|2-Player|Two[- ]Player)\b", row.get("name") or "")

    por_familia = collections.defaultdict(list)
    for row in rows:
        for f in familias(row):
            por_familia[f].append(str(row.get("maxplayers")) == "2")
    familia_de_dos = {f: sum(v) * 2 >= len(v) for f, v in por_familia.items()}

    tamanio = collections.Counter(f for row in rows for f in familias(row))
    miembros = collections.defaultdict(list)
    for row in rows:
        for f in familias(row):
            if familia_de_dos[f] or not es_duel(row):
                miembros[f].append(row)

    def coherente(juegos):
        """Hay un nombre base que comparte al menos el 60% de la familia
        (palabra completa: "Everdell" cubre "Everdell Farshore")."""
        bases = [nombre_base(j.get("name") or "") for j in juegos]
        mejor = max(sum(b == p or b.startswith(p + " ") for b in bases) for p in set(bases))
        return mejor / len(juegos) >= GRUPO_PREFIJO_COMUN_MIN

    def nombra_la_familia(familia, juegos):
        """Alternativa para familias grandes con nombres variados ("The Settlers
        of Catan", "Starfarers of Catan"): el 60% lleva el nombre de la familia."""
        nombre = re.sub(r"\s*\([^)]*\)$", "", familia.split(":", 1)[1].strip()).lower()
        if len(nombre) < 5:
            return False
        patron = re.compile(r"\b" + re.escape(nombre) + r"\b")
        return sum(bool(patron.search((j.get("name") or "").lower())) for j in juegos) / len(juegos) >= GRUPO_PREFIJO_COMUN_MIN

    validas = {f for f, juegos in miembros.items() if len(juegos) >= 2 and (coherente(juegos) or nombra_la_familia(f, juegos))}
    grupos = {}
    for row in rows:
        fs = [f for f in familias(row) if f in validas and row in miembros[f]]
        if fs:
            f = max(fs, key=lambda f: (tamanio[f], f))
            # sin "(Official)", "(Space Cowboys)"
            grupos[row["bgg_id"]] = re.sub(r"\s*\([^)]*\)$", "", f.split(":", 1)[1].strip())

    # Dentro de cada grupo, un juego con mecánicas o complejidad muy distintas
    # a las del principal (el más votado) es otro juego, no una variante.
    por_grupo = collections.defaultdict(list)
    for row in rows:
        if row["bgg_id"] in grupos:
            por_grupo[grupos[row["bgg_id"]]].append(row)

    def parecido(a, b):
        ma, mb = set(a.get("boardgamemechanic") or []), set(b.get("boardgamemechanic") or [])
        if ma and mb and len(ma & mb) / len(ma | mb) < GRUPO_MECANICAS_MIN:
            return False
        wa, wb = num(a.get("averageweight"), zero_is_missing=True), num(b.get("averageweight"), zero_is_missing=True)
        return wa is None or wb is None or abs(wa - wb) <= GRUPO_COMPLEJIDAD_MAX

    for nombre, juegos in por_grupo.items():
        principal = max(juegos, key=lambda j: num(j.get("usersrated")) or 0)
        # El nombre tiene que repetir el del juego original (el nombre del grupo o
        # el del principal, como palabra completa): "Wyrmspan" no es "Wingspan".
        base = nombre_base(principal.get("name") or "")
        patrones = [re.compile(r"\b" + re.escape(x.lower()) + r"\b") for x in {nombre, base} if len(x) >= 3]
        for j in juegos:
            nombra = any(p.search((j.get("name") or "").lower()) for p in patrones)
            if j is not principal and (not nombra or not parecido(principal, j)):
                del grupos[j["bgg_id"]]
        if sum(g == nombre for g in grupos.values()) < 2:  # quedó uno solo
            for j in juegos:
                grupos.pop(j["bgg_id"], None)
    return grupos


def build_game(row, grupo):
    """Una fila de integrated_data.jsonl (campos crudos de BGG) -> el juego
    que consume el sitio, con las columnas ya construidas."""
    game = {}
    for key in PASSTHROUGH:
        value = row.get(key)
        game[key] = (value.strip() if isinstance(value, str) else value) or None
    if row.get("notas"):  # tus notas (ver nota.py); el sitio las muestra solo con tu usuario de BGG. Sin notas no hay clave (no engorda las 28.000 fichas).
        game["notas"] = row["notas"]
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
        **precio_cazagangas(row),
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
