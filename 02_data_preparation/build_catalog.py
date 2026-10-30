"""Catálogo para el MVP multiusuario (branch mvp, ver MVP.md): todos los
juegos con las mismas columnas derivadas que data.json, pero sin lo que
depende de una colección en particular (`estado`, `mi_puntaje`). Esos dos
campos los pone el navegador a partir de la colección del visitante.

Escribe, en docs/data/:
- names.json: [bgg_id, nombre] de todos los juegos (buscador).
- index.json: los campos para filtrar, ordenar y armar tarjetas, como listas,
  más `tramo` (en qué games/NNN.json está la ficha completa).
- games/NNN.json: fichas completas {bgg_id: juego}, GAMES_PER_SHARD por archivo,
  en orden de ranking BGG (los sin ranking, al final, por reviews).

No toca docs/data/data.json. Corre después de integrate_data.py.
"""
import json
import shutil
from pathlib import Path

from construct_data import build_games

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


def write_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def main():
    games = build_games()
    for g in games:
        for field in USER_FIELDS:
            g.pop(field, None)
    # Tramos por popularidad (ranking, y sin ranking por reviews): una página de
    # ~60 tarjetas ordenadas por ranking cae en pocos tramos, no en todos.
    games.sort(key=lambda g: (g["ranking_bgg"] is None, g["ranking_bgg"] or 0, -(g["reviews_bgg"] or 0), int(g["bgg_id"])))
    for i, g in enumerate(games):
        g["tramo"] = i // GAMES_PER_SHARD

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    write_json(OUTPUT_DIR / "names.json", {"cols": ["bgg_id", "nombre"], "rows": [[g["bgg_id"], g["nombre"]] for g in games]})
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
