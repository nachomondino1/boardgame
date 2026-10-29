"""Refresca desde BGG, con tu token, dos cosas crudas:

1. Tu colección (bgg_collection.jsonl): qué juegos tenés (Own), tuviste,
   querés comprar, y el puntaje que les pusiste.
2. Los datos de cada juego (bgg_data.jsonl): puntaje, ranking, votos,
   marketplace, etc. Solo toca los campos pedidos de las filas pedidas, y un
   valor que BGG no devuelve nunca borra uno ya cargado. Un juego de tu
   colección sin fila todavía en bgg_data.jsonl se agrega, con todos sus campos.

Por default refresca los juegos de tu colección; con --top N suma además los
N mejor rankeados de bgg_data.jsonl (por `Board Game Rank`, el último que se
tenga guardado); con --scope all, todo bgg_data.jsonl (miles de requests: ~5s
por lote de 20).

Con --discover, antes de refrescar busca juegos nuevos: pide el "hot" de BGG,
y los que no están en bgg_data.jsonl se agregan (con todos sus campos) si
entran en el ranking --top N (sin --top, se agregan todos los hot). Es lo
único que la API permite para encontrar juegos nuevos.

--fields acepta nombres de campo separados por coma, o un atajo:
  volatile (default)  los que cambian seguido
  all                 todos los campos que trae la API (menos description)

Necesita BGG_TOKEN y BGG_USERNAME en .env.

Uso:
    python3 01_data_understanding/collect_initial_data/bgg/refresh_bgg_data.py --dry-run
    python3 01_data_understanding/collect_initial_data/bgg/refresh_bgg_data.py
    python3 01_data_understanding/collect_initial_data/bgg/refresh_bgg_data.py --top 300 --fields all
    python3 01_data_understanding/collect_initial_data/bgg/refresh_bgg_data.py --fields all --dry-run
    python3 01_data_understanding/collect_initial_data/bgg/refresh_bgg_data.py --fields averageweight,suggested_num_players
"""
import argparse
import datetime
import sys
import time

from bgg_common import (
    BGG_DATA_PATH, BGG_CACHE_FIELDS, COLLECTION_PATH,
    fetch_collection, fetch_hot_ids, fetch_things, load_collection, load_env,
    load_bgg_cache, upsert_bgg_cache, write_collection,
)

VOLATILE_FIELDS = [
    "usersrated", "average", "bayesaverage", "Board Game Rank", "averageweight",
    "owned", "wishing", "marketplacelistings",
]
ALL_FIELDS = [f for f in BGG_CACHE_FIELDS if f not in ("bgg_id", "description", "fecha_actualizacion")]

LOG_PATH = BGG_DATA_PATH.parents[2] / "01_data_understanding" / "refresh_log.md"
LOG_HEADER = (
    "# Registro de actualizaciones de BGG\n\n"
    "Una fila por cada corrida de `refresh_bgg_data.py` (la escribe el script solo, no a mano).\n\n"
    "| Fecha | Opciones | Juegos consultados | Con datos distintos | Cambios de campos | Juegos nuevos | No devueltos por BGG | Colección | Duración |\n"
    "|---|---|---|---|---|---|---|---|---|\n"
)


def write_log(args, consultados, con_cambios, cambios, nuevos, no_devueltos, coleccion, segundos):
    """Suma una fila al registro de corridas (data/ está gitignored; este log vive
    junto a los scripts y se versiona)."""
    if not LOG_PATH.exists():
        LOG_PATH.write_text(LOG_HEADER, encoding="utf-8")
    opciones = " ".join(a for a in (f"--scope {args.scope}", f"--top {args.top}" if args.top else "",
                                    "--discover" if args.discover else "", f"--fields {args.fields}",
                                    f"--limit {args.limit}" if args.limit else "") if a)
    minutos, seg = divmod(int(segundos), 60)
    with LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(f"| {datetime.date.today().isoformat()} | `{opciones}` | {consultados} | {con_cambios} | {cambios} | "
                f"{nuevos} | {no_devueltos} | {coleccion} | {minutos} min {seg} s |\n")



def resolve_fields(spec):
    if spec == "volatile":
        return list(VOLATILE_FIELDS)
    if spec == "all":
        return list(ALL_FIELDS)
    fields = [f.strip() for f in spec.split(",") if f.strip()]
    unknown = [f for f in fields if f not in BGG_CACHE_FIELDS]
    if unknown:
        sys.exit(f"Campo(s) desconocido(s): {', '.join(unknown)}. Válidos: {', '.join(BGG_CACHE_FIELDS)}")
    return fields


def refresh_collection(dry_run):
    """Baja tu colección, muestra qué cambió respecto a la última vez y la
    guarda. Devuelve las filas."""
    rows = fetch_collection(load_env("BGG_USERNAME"))
    previous = {r["bgg_id"]: r for r in load_collection()}
    changed = [r for r in rows if previous.get(r["bgg_id"]) != r]
    print(f"Colección: {len(rows)} juego(s), {len(changed)} nuevo(s) o con cambios")
    for r in changed[:20]:
        print(f"  {r['bgg_id']} {r['name']}")
    if not dry_run:
        write_collection(rows)
    return rows


def discover_hot(top, dry_run):
    """Agrega a bgg_data.jsonl los juegos del "hot" de BGG que todavía no
    están, si están dentro del top N del ranking (o todos, sin top)."""
    known = {r["bgg_id"] for r in load_bgg_cache()}
    nuevos = [i for i in fetch_hot_ids() if i not in known]
    print(f"Hot de BGG: {len(nuevos)} juego(s) que no están en el catálogo")
    if not nuevos:
        return 0
    fetched = fetch_things(nuevos, marketplace=True)
    to_add = {}
    for bgg_id, attrs in fetched.items():
        rank = attrs.get("Board Game Rank") or ""
        dentro = (not top) or (rank.isdigit() and int(rank) <= top)
        print(f"  {'+' if dentro else '-'} {attrs['name']} (bgg_id={bgg_id}, ranking: {rank or 'sin ranking'})")
        if dentro:
            to_add[bgg_id] = attrs
    if to_add and not dry_run:
        upsert_bgg_cache(to_add)
    print(f"  {len(to_add)} agregado(s)" + (" (dry-run)" if dry_run else ""))
    return len(to_add)


def main():
    parser = argparse.ArgumentParser(description="Refresca tu colección y los datos de BGG de tus juegos")
    parser.add_argument("--scope", choices=["coleccion", "all"], default="coleccion")
    parser.add_argument("--top", type=int, help="suma los N mejor rankeados (Board Game Rank) a los juegos a refrescar")
    parser.add_argument("--discover", action="store_true", help="antes de refrescar, agrega juegos nuevos del hot de BGG (ver --top)")
    parser.add_argument("--fields", default="volatile", help="coma-separados, o volatile | all")
    parser.add_argument("--dry-run", action="store_true", help="muestra el diff sin escribir")
    parser.add_argument("--limit", type=int, help="solo los primeros N juegos (para probar)")
    args = parser.parse_args()

    inicio = time.time()
    hoy = datetime.date.today().isoformat()
    fields = resolve_fields(args.fields)
    collection = refresh_collection(args.dry_run)
    descubiertos = discover_hot(args.top, args.dry_run) if args.discover else 0

    cache = {r["bgg_id"]: r for r in load_bgg_cache() if r.get("bgg_id")}
    ids = [r["bgg_id"] for r in collection] if args.scope == "coleccion" else sorted(cache, key=int)
    if args.top:
        ranked = sorted((r for r in cache.values() if (r.get("Board Game Rank") or "").isdigit()),
                        key=lambda r: int(r["Board Game Rank"]))[: args.top]
        ids += [r["bgg_id"] for r in ranked if r["bgg_id"] not in ids]
    if args.limit:
        ids = ids[: args.limit]
    nuevos = [i for i in ids if i not in cache]
    print(f"{len(ids)} juego(s) ({len(nuevos)} sin datos todavía), {len(fields)} campo(s): {', '.join(fields)}")

    fetched = fetch_things(
        ids,
        marketplace="marketplacelistings" in fields or bool(nuevos),
        progress=lambda done, total: print(f"  {done}/{total}"),
    )

    updates, changes, no_devueltos = {}, 0, 0
    for bgg_id in ids:
        attrs = fetched.get(bgg_id)
        if attrs is None:
            print(f"  bgg_id={bgg_id}: BGG no lo devolvió, no se toca.", file=sys.stderr)
            no_devueltos += 1
            continue
        row_updates = {"fecha_actualizacion": hoy}
        for field in (ALL_FIELDS if bgg_id in nuevos else fields):
            new, old = attrs.get(field), cache.get(bgg_id, {}).get(field)
            if new in (None, "", []):
                continue  # nunca borrar un dato ya cargado con un vacío
            if new != old:
                row_updates[field] = new
                if changes < 40:
                    print(f"  {bgg_id} {field}: {str(old)[:40]!r} -> {str(new)[:40]!r}")
                changes += 1
        updates[bgg_id] = row_updates

    con_cambios = sum(1 for u in updates.values() if len(u) > 1)
    print(f"{changes} cambio(s) en {con_cambios} juego(s), {len(updates)} con fecha_actualizacion al día" + (" (dry-run, no se escribió nada)" if args.dry_run else ""))
    if updates and not args.dry_run:
        added, updated = upsert_bgg_cache(updates)
        print(f"OK: {added} fila(s) nueva(s) y {updated} actualizada(s) en {BGG_DATA_PATH.name}; colección en {COLLECTION_PATH.name}.")
        write_log(args, len(updates), con_cambios, changes, descubiertos, no_devueltos, len(collection), time.time() - inicio)
        print(f"Registro en {LOG_PATH}")


if __name__ == "__main__":
    main()
