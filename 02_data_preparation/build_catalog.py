"""Catálogo para el MVP multiusuario (branch mvp, ver MVP.md): todos los
juegos con las mismas columnas derivadas que data.json, pero sin lo que
depende de una colección en particular (`estado`, `mi_puntaje`). Esos dos
campos los pone el navegador a partir de la colección del visitante.

Escribe, en docs/data/:
- names.json: [bgg_id, nombre, alternativos, anio] de todos los juegos (buscador; el año distingue
  homónimos, p. ej. dos "Gaudí"). Los alternativos (alfabeto latino, separados por "|", "" si no hay): así se encuentra
  "Cazabombas" aunque el nombre principal sea "Bomb Busters".
- meta.json: fecha de la última actualización de datos de BGG y cuántos juegos la tienen.
- index.json: los campos para filtrar, ordenar y armar tarjetas, como listas,
  más `tramo` (en qué games/NNN.json está la ficha completa).
- games/NNN.json: fichas completas {bgg_id: juego}, GAMES_PER_SHARD por archivo,
  en orden de ranking BGG (los sin ranking, al final, por reviews).

No toca docs/data/data.json. Corre después de integrate_data.py.
"""
import json
import re
import shutil
import unicodedata
from pathlib import Path

from construct_data import INTEGRATED_DATA_PATH, build_games

ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = ROOT / "docs" / "data"
SHARDS_DIR = OUTPUT_DIR / "games"
USER_FIELDS = ("estado", "mi_puntaje")
GAMES_PER_SHARD = 500
INDEX_FIELDS = (
    "bgg_id", "nombre", "jug_min", "jug_max", "jug_best_min", "jug_best_max",
    "duracion", "complejidad", "puntaje_bgg", "reviews_bgg", "ranking_bgg",
    "grupo", "anio", "modo", "precio_ref_usd", "precio_ars", "precio_ars_visto",
)


# Mecánicas que dicen "de qué va" un juego, de más a menos identificatorias (clave de BGG, nombre corto).
# El índice guarda por juego los números de esta lista (columna "mecs") y la lista misma ("mecanicas"):
# con eso el sitio muestra las mecánicas en la card y las filtra sin pedir la ficha de cada juego.
# Las mecánicas técnicas (Hexagon Grid, Modular Board, End Game Bonuses...) quedan afuera a propósito.
MECANICAS_CLAVE = [
    ("Worker Placement", "Worker Placement"),
    ("Deck, Bag, and Pool Building", "Deck Building"),
    ("Area Majority / Influence", "Area Control"),
    ("Tile Placement", "Tile Placement"),
    ("Network and Route Building", "Route Building"),
    ("Open Drafting", "Drafting"),
    ("Auction / Bidding", "Auction"),
    ("Trick-taking", "Trick-taking"),
    ("Set Collection", "Set Collection"),
    ("Pick-up and Deliver", "Pick-up & Deliver"),
    ("Push Your Luck", "Push Your Luck"),
    ("Hand Management", "Hand Management"),
    ("Dice Rolling", "Dice Rolling"),
    ("Pattern Building", "Pattern Building"),
    ("Trading", "Trading"),
    ("Deduction", "Deduction"),
    ("Memory", "Memory"),
    ("Voting", "Voting"),
    ("Betting and Bluffing", "Bluffing"),
    ("Take That", "Take That"),
    ("Storytelling", "Storytelling"),
    ("Role Playing", "Role Playing"),
    ("Scenario / Mission / Campaign Game", "Campaign"),
    ("Campaign / Battle Card Driven", "Card Driven"),
    ("Roll / Spin and Move", "Roll & Move"),
    ("Race", "Race"),
    ("Stock Holding", "Stock Holding"),
    ("Real-Time", "Real-Time"),
    ("Action Queue", "Action Queue"),
    ("Area Movement", "Area Movement"),
    ("Action Points", "Action Points"),
    ("Variable Player Powers", "Player Powers"),
    ("Simultaneous Action Selection", "Simultaneous Actions"),
    ("Pattern Recognition", "Pattern Recognition"),
    ("Paper-and-Pencil", "Paper & Pencil"),
]
MECANICA_ID = {bgg: i for i, (bgg, _) in enumerate(MECANICAS_CLAVE)}


# Precisión del índice: la que se ve en el sitio (puntaje y complejidad con 2 decimales, precio entero). Las fichas
# (games/NNN.json) conservan los valores completos.
REDONDEO_INDICE = {"puntaje_bgg": 2, "complejidad": 2, "precio_ref_usd": 0, "precio_ars": 0}


def valor_indice(campo, valor):
    n = REDONDEO_INDICE.get(campo)
    if n is None or not isinstance(valor, (int, float)):
        return valor
    return int(round(valor)) if n == 0 else round(valor, n)


def mecanicas_clave(game):
    """Números (en MECANICAS_CLAVE, de más a menos identificatoria) de las mecánicas clave del juego, o None."""
    ids = sorted({MECANICA_ID[m] for m in game.get("mecanicas") or [] if m in MECANICA_ID})
    return ids or None


def plain(text):
    """Minúsculas y sin acentos, para comparar nombres."""
    return "".join(c for c in unicodedata.normalize("NFD", text.lower()) if unicodedata.category(c) != "Mn")


def latin_alternates(name, alternates):
    """Alternativos con alfabeto latino (el resto -cirílico, CJK, árabe- no se puede buscar con un teclado
    en español), sin repetir el nombre principal ni entre sí."""
    seen = {plain(name)}
    result = []
    for alt in alternates or []:
        key = plain(alt)
        if key in seen or not re.search(r"[a-z0-9]", key):
            continue
        seen.add(key)
        result.append(alt)
    return result


IA_DIR = OUTPUT_DIR / "ia"
IA_MAX_CATALOGO = 2000  # los mejores por ranking; el resto no entra para que el archivo siga siendo liviano
IA_MAX_TAJADA = 300
IA_JUGADORES_MAX = 6  # la última tajada es "6 o más"
IA_ENCABEZADO = (
    "Catálogo de juegos de mesa (datos de BoardGameGeek) para recomendar compras. Una línea por juego: "
    "ranking BGG, nombre (año), puntaje BGG, complejidad de 1 a 5, jugadores posibles (ideal), duración, tipo y mecánicas, "
    "y precio en Argentina (en pesos si hay precio real de una tienda; si no, el precio de referencia del marketplace de BGG en USD, "
    "que es solo una guía)."
)


def linea_ia(g):
    jug = None
    if g.get("jug_min") is not None and g.get("jug_max") is not None:
        jug = f"{g['jug_min']}" if g["jug_min"] == g["jug_max"] else f"{g['jug_min']}-{g['jug_max']}"
        lo, hi = g.get("jug_best_min"), g.get("jug_best_max")
        if lo is None:
            lo = hi
        if hi is None:
            hi = lo
        if lo is not None:
            jug += f" jug. (ideal {lo if lo == hi else f'{lo}-{hi}'})"
        else:
            jug += " jug."
    ids = mecanicas_clave(g) or []
    mecs = ", ".join(MECANICAS_CLAVE[i][1] for i in ids[:3])
    if g.get("precio_ars") is not None:
        precio = f"${round(g['precio_ars']):,}".replace(",", ".") + " ARS"
    elif g.get("precio_ref_usd") is not None:
        precio = f"ref. US${round(g['precio_ref_usd'])}"
    else:
        precio = None
    partes = [
        f"BGG {g['puntaje_bgg']:.1f}" if g.get("puntaje_bgg") is not None else None,
        f"complejidad {g['complejidad']:.1f}" if g.get("complejidad") is not None else None,
        jug,
        f"{g['duracion']} min" if g.get("duracion") else None,
        g["modo"].replace("_", " ") if g.get("modo") else None,
        mecs or None,
        precio,
    ]
    rank = f"#{g['ranking_bgg']} " if g.get("ranking_bgg") is not None else ""
    anio = f" ({g['anio']})" if g.get("anio") else ""
    return f"{rank}{g['nombre']}{anio}: " + " · ".join(p for p in partes if p)


def escribir_catalogo_ia(games):
    """Archivos de texto para que un chat de IA con acceso a links lea el catálogo: catalogo.txt (los mejores por ranking)
    y una tajada por cantidad ideal de jugadores (jugadores-N.txt)."""
    if IA_DIR.exists():
        shutil.rmtree(IA_DIR)
    IA_DIR.mkdir(parents=True)
    vistos = set()
    unicos = []
    for g in games:  # ya vienen por ranking; una sola edición por grupo
        clave = g.get("grupo") or g["bgg_id"]
        if g.get("ranking_bgg") is None or clave in vistos:
            continue
        vistos.add(clave)
        unicos.append(g)

    def escribir(nombre, titulo, lista):
        texto = f"{titulo}\n{IA_ENCABEZADO}\n\n" + "\n".join(linea_ia(g) for g in lista) + "\n"
        (IA_DIR / nombre).write_text(texto, encoding="utf-8")

    escribir("catalogo.txt", f"{min(len(unicos), IA_MAX_CATALOGO)} mejores juegos por ranking de BGG.", unicos[:IA_MAX_CATALOGO])
    for n in range(1, IA_JUGADORES_MAX + 1):
        def ideal(g):
            lo, hi = g.get("jug_best_min"), g.get("jug_best_max")
            lo = hi if lo is None else lo
            hi = lo if hi is None else hi
            return lo is not None and (hi >= n if n == IA_JUGADORES_MAX else lo <= n <= hi)
        etiqueta = f"{n} o más" if n == IA_JUGADORES_MAX else f"{n}"
        escribir(f"jugadores-{n}.txt", f"Mejores juegos por ranking de BGG que son ideales para {etiqueta} jugadores.",
                 [g for g in unicos if ideal(g)][:IA_MAX_TAJADA])


def write_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def main():
    games = build_games()
    with INTEGRATED_DATA_PATH.open(encoding="utf-8") as f:
        raw = {r["bgg_id"]: r for r in (json.loads(line) for line in f if line.strip())}
    for g in games:
        for field in USER_FIELDS:
            g.pop(field, None)
    # Tramos por popularidad (ranking, y sin ranking por reviews): una página de
    # ~60 tarjetas ordenadas por ranking cae en pocos tramos, no en todos.
    games.sort(key=lambda g: (g["ranking_bgg"] is None, g["ranking_bgg"] or 0, -(g["reviews_bgg"] or 0), int(g["bgg_id"])))
    for i, g in enumerate(games):
        g["tramo"] = i // GAMES_PER_SHARD

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    names = []
    for g in games:
        alts = latin_alternates(g["nombre"], raw[g["bgg_id"]].get("alternate"))
        names.append([g["bgg_id"], g["nombre"], "|".join(alts), g.get("anio")])
    write_json(OUTPUT_DIR / "names.json", {"cols": ["bgg_id", "nombre", "alternativos", "anio"], "rows": names})

    # Fecha de los datos de BGG: la de la actualización principal (la más frecuente). Los pocos juegos
    # agregados después (p. ej. los que aparecen en Cazagangas) tienen una fecha posterior y no la cambian.
    fechas = [raw[g["bgg_id"]].get("fecha_actualizacion") for g in games]
    fechas = [d for d in fechas if d]
    principal = max(set(fechas), key=fechas.count) if fechas else None
    write_json(OUTPUT_DIR / "meta.json", {
        "actualizado": principal,
        "juegos_actualizados": fechas.count(principal) if fechas else 0,
        "juegos_total": len(games),
        # Día del precio de Cazagangas más reciente (los precios reales son de ahí, no de la fecha de BGG).
        "precios_cazagangas": max((d for d in (raw[g["bgg_id"]].get("fecha_precio_cazagangas") for g in games) if d), default=None),
    })
    write_json(OUTPUT_DIR / "index.json", {
        "cols": list(INDEX_FIELDS) + ["mecs", "tramo"],
        "mecanicas": [corto for _, corto in MECANICAS_CLAVE],
        "rows": [[valor_indice(c, g.get(c)) for c in INDEX_FIELDS] + [mecanicas_clave(g), g["tramo"]] for g in games],
    })

    if SHARDS_DIR.exists():
        shutil.rmtree(SHARDS_DIR)  # que no queden tramos de una corrida anterior con más juegos
    SHARDS_DIR.mkdir(parents=True)
    n_shards = games[-1]["tramo"] + 1
    for shard in range(n_shards):
        ficha = {g["bgg_id"]: g for g in games[shard * GAMES_PER_SHARD:(shard + 1) * GAMES_PER_SHARD]}
        write_json(SHARDS_DIR / f"{shard:03d}.json", ficha)
    escribir_catalogo_ia(games)
    print(f"OK: {len(games)} juegos en names.json, index.json y {n_shards} tramos en {SHARDS_DIR}")


if __name__ == "__main__":
    main()
