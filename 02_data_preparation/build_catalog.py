"""Catálogo para el MVP multiusuario (branch mvp, ver MVP.md): todos los
juegos con las mismas columnas derivadas que data.json, pero sin lo que
depende de una colección en particular (`estado`, `mi_puntaje`). Esos dos
campos los pone el navegador a partir de la colección del visitante.

Escribe, en docs/data/:
- names.json: [bgg_id, nombre] de todos los juegos (buscador), con un tercer elemento (nombres
  alternativos en alfabeto latino, separados por "|") cuando el juego los tiene: así se encuentra
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
    "grupo", "anio", "modo", "puntaje_ajust_bgg",
)


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
        names.append([g["bgg_id"], g["nombre"], "|".join(alts)] if alts else [g["bgg_id"], g["nombre"]])
    write_json(OUTPUT_DIR / "names.json", {"cols": ["bgg_id", "nombre", "alternativos"], "rows": names})

    # Última actualización de datos de BGG: la fecha más reciente, y cuántos juegos tienen fecha
    # (los que nunca se refrescaron con la API vienen de la copia de 2025 con que arrancó el catálogo).
    fechas = [raw[g["bgg_id"]].get("fecha_actualizacion") for g in games]
    fechas = [d for d in fechas if d]
    write_json(OUTPUT_DIR / "meta.json", {
        "actualizado": max(fechas) if fechas else None,
        "juegos_actualizados": sum(1 for d in fechas if d == max(fechas)) if fechas else 0,
        "juegos_total": len(games),
    })
    write_json(OUTPUT_DIR / "index.json", {
        "cols": list(INDEX_FIELDS) + ["tramo"],
        "rows": [[g.get(c) for c in INDEX_FIELDS] + [g["tramo"]] for g in games],
    })

    if SHARDS_DIR.exists():
        shutil.rmtree(SHARDS_DIR)  # que no queden tramos de una corrida anterior con más juegos
    SHARDS_DIR.mkdir(parents=True)
    n_shards = games[-1]["tramo"] + 1
    for shard in range(n_shards):
        ficha = {g["bgg_id"]: g for g in games[shard * GAMES_PER_SHARD:(shard + 1) * GAMES_PER_SHARD]}
        write_json(SHARDS_DIR / f"{shard:03d}.json", ficha)
    print(f"OK: {len(games)} juegos en names.json, index.json y {n_shards} tramos en {SHARDS_DIR}")


if __name__ == "__main__":
    main()
