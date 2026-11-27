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

Con --add <id o nombre> agrega un juego puntual: si es un nombre, lo busca en la
API de BGG (endpoint `search`), y trae todos sus campos. Todo juego que entra
nuevo al catálogo (por --add, por --discover o por tu colección) busca además
su link de Cazagangas, probando el nombre principal y los alternativos.

Con --discover, antes de refrescar busca juegos nuevos: pide el "hot" de BGG,
y los que no están en bgg_data.jsonl se agregan (con todos sus campos) si
entran en el ranking --top N (sin --top, se agregan todos los hot). Es lo
único que la API permite para encontrar juegos nuevos.

Con --scan-ids se barren los ids de BGG hacia arriba (los juegos nuevos tienen ids altos) y se agregan los
que son juegos y ya entran en el ranking --top N. Es la forma de encontrar juegos nuevos que nunca estuvieron en el
"hot" (Moon Colony Bloodbath, puesto 401, no estaba). Recuerda hasta qué id llegó en bgg_scan_ids.json, así que cada
corrida solo mira los ids nuevos; la primera arranca en --desde (default 430000, donde se corta el snapshot de
Hugging Face) y puede tardar horas (5 s por cada 20 ids). Los juegos recientes que todavía no tienen ranking pero ya
tienen votos quedan en "seguimiento" y se vuelven a mirar en cada corrida, porque BGG los rankea después.

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
import json
import statistics
import sys
import time
import urllib.parse
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "cazagangas"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from logs_actualizacion_data import LOG_PATH, write_logs_actualizacion_data  # noqa: E402
from cazagangas_common import load_cazagangas_cache, resolver_link  # noqa: E402
from bgg_common import (  # noqa: E402
    API_URL, BGG_DATA_PATH, BGG_CACHE_FIELDS, COLLECTION_PATH, http_get,
    fetch_collection, fetch_hot_ids, fetch_things, load_collection, load_env,
    load_bgg_cache, upsert_bgg_cache, write_collection,
    load_watch, move_to_watch, restore_from_watch,
)

VOLATILE_FIELDS = [
    "usersrated", "average", "bayesaverage", "Board Game Rank", "averageweight",
    "owned", "wishing", "marketplacelistings",
]
CHUNK_SIZE = 500  # juegos por tanda (25 requests): se guarda al terminar cada una
ALL_FIELDS = [f for f in BGG_CACHE_FIELDS if f not in ("bgg_id", "description", "fecha_actualizacion")]

def resumen_control(con_cambios, actualizados, deltas):
    """Texto de control: qué tanto cambiaron los datos. Si cambia todo o nada, algo anduvo mal."""
    partes = [f"cambiaron valores en {con_cambios} de {actualizados} filas"]
    r, v, p = deltas["Board Game Rank"], deltas["usersrated"], deltas["average"]
    if r:
        partes.append(f"ranking: se movió en {len(r)} filas, mediana {statistics.median(abs(x) for x in r):.0f} puestos")
    if v:
        partes.append(f"votos: {statistics.mean(v):+.0f} en promedio")
    if p:
        partes.append(f"puntaje: {statistics.mean(p):+.3f} en promedio")
    return "; ".join(partes)


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


def search_game(term):
    """bgg_id de `term` (un id, o un nombre buscado en la API de BGG; si hay
    varios con el mismo nombre exacto o ninguno exacto, corta y los lista)."""
    if term.strip().isdigit():
        return term.strip()
    root = ET.fromstring(http_get(
        f"{API_URL.replace('/thing', '/search')}?type=boardgame&query={urllib.parse.quote(term)}", authorized=True))
    items = [(i.get("id"), i.find("name").get("value"), (i.find("yearpublished") or ET.Element("x")).get("value", ""))
             for i in root.findall("item")]
    exactos = [x for x in items if x[1].lower() == term.strip().lower()]
    if len(exactos) == 1:
        return exactos[0][0]
    candidatos = exactos or items[:10]
    sys.exit(("Más de uno con ese nombre" if exactos else f"Sin coincidencia exacta para \"{term}\"")
             + ", usá el bgg_id:\n  " + "\n  ".join(f"{i}  {n} ({y})" for i, n, y in candidatos)
             if candidatos else f"No encontré ningún juego llamado \"{term}\" en BGG.")


def resolve_cazagangas(juegos, dry_run):
    """Busca el link de Cazagangas de cada juego nuevo ({bgg_id: attrs}) que
    todavía no tenga uno: prueba el nombre principal y después los alternativos."""
    ya = load_cazagangas_cache()
    for bgg_id, attrs in juegos.items():
        if bgg_id in ya or dry_run:
            continue
        url, status = resolver_link([attrs.get("name", "")] + list(attrs.get("alternate") or []), bgg_id)
        print(f"  Cazagangas {attrs.get('name')}: " + (f"{url} (200)" if status == "200" else f"sin match verificado ({status})"))


def add_game(term, dry_run):
    """Agrega un juego puntual (id o nombre) con todos sus campos."""
    bgg_id = search_game(term)
    if bgg_id in {r["bgg_id"] for r in load_bgg_cache()}:
        sys.exit(f"\"{term}\" es el bgg_id {bgg_id}, que ya está en {BGG_DATA_PATH.name}.")
    attrs = fetch_things([bgg_id], marketplace=True).get(bgg_id)
    if attrs is None:
        sys.exit(f"BGG no devolvió el bgg_id {bgg_id}.")
    print(f"Agregando {attrs['name']} (bgg_id={bgg_id})" + (" (dry-run)" if dry_run else ""))
    if not dry_run:
        upsert_bgg_cache({bgg_id: {**attrs, "fecha_actualizacion": datetime.date.today().isoformat()}})
    return {bgg_id: attrs}


def agregar_por_ids(ids, dry_run=False):
    """Agrega al catálogo los juegos de BGG `ids` que todavía no están (con todos sus campos). Solo `boardgame`: una
    expansión (`boardgameexpansion`) u otro tipo no entra al catálogo. Es lo que usa load_cazagangas_prices.py para los
    juegos que Cazagangas tiene en stock y el catálogo no (el id sale de la tarjeta del listado).

    Devuelve {bgg_id: (estado, nombre)}, con estado "agregado", "expansion" (otro tipo) o "no_devuelto" (BGG no lo
    devuelve)."""
    hoy = datetime.date.today().isoformat()
    fetched = fetch_things(list(ids), marketplace=True)
    resultado, nuevos = {}, {}
    for bgg_id in ids:
        attrs = fetched.get(bgg_id)
        if attrs is None:
            resultado[bgg_id] = ("no_devuelto", None)
        elif attrs.get("type") != "boardgame":
            resultado[bgg_id] = ("expansion", attrs.get("name"))
        else:
            nuevos[bgg_id] = {**attrs, "fecha_actualizacion": hoy}
            resultado[bgg_id] = ("agregado", attrs.get("name"))
    if nuevos and not dry_run:
        upsert_bgg_cache(nuevos)
    return resultado


def discover_hot(top, dry_run):
    """Agrega a bgg_data.jsonl los juegos del "hot" de BGG que todavía no
    están, si están dentro del top N del ranking (o todos, sin top)."""
    known = {r["bgg_id"] for r in load_bgg_cache()}
    nuevos = [i for i in fetch_hot_ids() if i not in known]
    print(f"Hot de BGG: {len(nuevos)} juego(s) que no están en el catálogo")
    if not nuevos:
        return {}
    fetched = fetch_things(nuevos, marketplace=True)
    to_add = {}
    for bgg_id, attrs in fetched.items():
        rank = attrs.get("Board Game Rank") or ""
        dentro = (not top) or (rank.isdigit() and int(rank) <= top)
        print(f"  {'+' if dentro else '-'} {attrs['name']} (bgg_id={bgg_id}, ranking: {rank or 'sin ranking'})")
        if dentro:
            to_add[bgg_id] = attrs
    if to_add and not dry_run:
        upsert_bgg_cache({i: {**a, "fecha_actualizacion": datetime.date.today().isoformat()} for i, a in to_add.items()})
    print(f"  {len(to_add)} agregado(s)" + (" (dry-run)" if dry_run else ""))
    return to_add


SCAN_PATH = BGG_DATA_PATH.parent / "bgg_scan_ids.json"
SCAN_DESDE_DEFECTO = 430000   # por debajo de este id el snapshot inicial ya cubre (ver docstring)
SCAN_TANDA = 200              # ids por tanda: se guarda el avance al terminar cada una
SCAN_VACIAS_PARA_PARAR = 5    # tandas seguidas sin ningún item = se llegó al final de los ids existentes
SCAN_VOTOS_SEGUIMIENTO = 10   # un juego sin ranking con al menos tantos votos se vuelve a mirar (BGG rankea con 30)


def _cargar_scan():
    try:
        return json.loads(SCAN_PATH.read_text())
    except (OSError, ValueError):
        return {"ultimo_id": None, "seguimiento": {}}


def _guardar_scan(estado, dry_run):
    if not dry_run:
        SCAN_PATH.write_text(json.dumps(estado, ensure_ascii=False, indent=1))


def descubrir_por_ids(top, desde, max_ids, dry_run):
    """Barre ids de BGG por encima del último mirado y agrega al catálogo los juegos (no expansiones) que ya están
    dentro del top N del ranking. Devuelve {bgg_id: attrs} de los agregados."""
    estado = _cargar_scan()
    known = {r["bgg_id"] for r in load_bgg_cache()}
    hoy = datetime.date.today()
    agregados = {}

    def ranking_ok(attrs):
        rank = attrs.get("Board Game Rank") or ""
        return attrs.get("type") == "boardgame" and rank.isdigit() and int(rank) <= top

    def agregar(candidatos, origen):
        # Con marketplace (el barrido no lo pide, para no pesar) y recién ahí se guarda.
        fetched = fetch_things(list(candidatos), marketplace=True)
        nuevos = {i: {**a, "fecha_actualizacion": hoy.isoformat()} for i, a in fetched.items() if i not in known}
        for i, a in nuevos.items():
            print(f"  + {a['name']} (bgg_id={i}, ranking {a.get('Board Game Rank')}, {origen})", flush=True)
        if nuevos and not dry_run:
            upsert_bgg_cache(nuevos)
        known.update(nuevos)
        agregados.update(nuevos)

    # 1) Seguimiento: juegos recientes que no tenían ranking la última vez.
    seg = estado.get("seguimiento", {})
    if seg:
        print(f"Seguimiento: {len(seg)} juego(s) recientes sin ranking, se vuelven a mirar", flush=True)
        fetched = fetch_things(list(seg))
        listos = [i for i, a in fetched.items() if i not in known and ranking_ok(a)]
        if listos:
            agregar(listos, "ya rankeado")
        for i in list(seg):
            a = fetched.get(i)
            if a is None or i in known or int(a.get("yearpublished") or 0) < hoy.year - 1 or a.get("Board Game Rank", "").isdigit():
                seg.pop(i, None)

    # 2) Ids nuevos.
    ultimo = estado.get("ultimo_id")
    inicio = (ultimo + 1) if ultimo else desde
    print(f"Barrido de ids desde {inicio} (top {top})", flush=True)
    vacias, revisados, actual = 0, 0, inicio
    while vacias < SCAN_VACIAS_PARA_PARAR and (not max_ids or revisados < max_ids):
        ids = [str(i) for i in range(actual, actual + SCAN_TANDA)]
        time.sleep(5)
        fetched = fetch_things(ids)
        vacias = 0 if fetched else vacias + 1
        candidatos = [i for i, a in fetched.items() if i not in known and ranking_ok(a)]
        for i, a in fetched.items():
            if i in known or i in candidatos or a.get("type") != "boardgame" or (a.get("Board Game Rank") or "").isdigit():
                continue
            if int(a.get("usersrated") or 0) >= SCAN_VOTOS_SEGUIMIENTO and int(a.get("yearpublished") or 0) >= hoy.year - 1:
                seg[i] = a.get("name", "")
        if candidatos:
            time.sleep(5)
            agregar(candidatos, "barrido")
        actual += SCAN_TANDA
        revisados += SCAN_TANDA
        estado["ultimo_id"] = actual - 1
        estado["seguimiento"] = seg
        _guardar_scan(estado, dry_run)
        if revisados % 2000 == 0:
            print(f"  ... hasta el id {actual - 1}, {len(agregados)} agregado(s), {len(seg)} en seguimiento", flush=True)
    print(f"Barrido listo hasta el id {estado['ultimo_id']}: {len(agregados)} agregado(s), {len(seg)} en seguimiento"
          + (" (dry-run: el avance no se guardó)" if dry_run else ""), flush=True)
    return agregados


def main():
    parser = argparse.ArgumentParser(description="Refresca tu colección y los datos de BGG de tus juegos")
    parser.add_argument("--scope", choices=["coleccion", "all"], default="coleccion")
    parser.add_argument("--add", metavar="ID_O_NOMBRE", help="agrega un juego puntual al catálogo (busca el nombre en la API de BGG)")
    parser.add_argument("--top", type=int, help="suma los N mejor rankeados (Board Game Rank) a los juegos a refrescar")
    parser.add_argument("--discover", action="store_true", help="antes de refrescar, agrega juegos nuevos del hot de BGG (ver --top)")
    parser.add_argument("--scan-ids", action="store_true", help="barre los ids nuevos de BGG y agrega los que entran en --top (ver docstring)")
    parser.add_argument("--desde", type=int, default=SCAN_DESDE_DEFECTO, help="primer id del barrido si todavía no hay avance guardado")
    parser.add_argument("--max-ids", type=int, help="tope de ids a barrer en esta corrida (para probar)")
    parser.add_argument("--fields", default="volatile", help="coma-separados, o volatile | all")
    parser.add_argument("--dry-run", action="store_true", help="muestra el diff sin escribir")
    parser.add_argument("--skip-fresh", action="store_true", help="saltea los juegos ya actualizados hoy (para retomar una corrida cortada)")
    parser.add_argument("--stale", action="store_true", help="solo los juegos que todavía no se actualizaron nunca desde la API (vienen de la copia de 2025)")
    parser.add_argument("--limit", type=int, help="solo los primeros N juegos (para probar)")
    parser.add_argument("--motivo", default="", help="por qué corrés esto (columna motivo de logs_actualizacion_data.csv)")
    parser.add_argument("--nota", default="", help="observación para logs_actualizacion_data.csv (por qué se corre)")
    args = parser.parse_args()

    inicio = time.time()
    hoy = datetime.date.today().isoformat()
    fields = resolve_fields(args.fields)
    collection = refresh_collection(args.dry_run)
    descubiertos = discover_hot(args.top, args.dry_run) if args.discover else {}
    agregados = add_game(args.add, args.dry_run) if args.add else {}
    barridos = descubrir_por_ids(args.top or 5000, args.desde, args.max_ids, args.dry_run) if args.scan_ids else {}
    resolve_cazagangas({**descubiertos, **agregados, **barridos}, args.dry_run)

    # Los que están en vigilancia se vuelven a preguntar: si BGG los devuelve otra vez, vuelven al catálogo.
    en_vigilancia = [r["bgg_id"] for r in load_watch()]
    if en_vigilancia and not args.dry_run:
        try:
            vueltos = restore_from_watch(fetch_things(en_vigilancia), hoy)
            if vueltos:
                print(f"{vueltos} juego(s) en vigilancia volvieron a aparecer en BGG y se restauraron.")
        except Exception as e:  # noqa: BLE001 — la vigilancia no frena el refresh
            print(f"No pude re-chequear los juegos en vigilancia: {e}", file=sys.stderr)

    cache = {r["bgg_id"]: r for r in load_bgg_cache() if r.get("bgg_id")}
    ids = [r["bgg_id"] for r in collection] if args.scope == "coleccion" else sorted(cache, key=int)
    if args.top:
        ranked = sorted((r for r in cache.values() if (r.get("Board Game Rank") or "").isdigit()),
                        key=lambda r: int(r["Board Game Rank"]))[: args.top]
        ids += [r["bgg_id"] for r in ranked if r["bgg_id"] not in ids]
    if args.stale:
        ids = [i for i in ids if not cache.get(i, {}).get("fecha_actualizacion")]
    if args.skip_fresh:
        ids = [i for i in ids if cache.get(i, {}).get("fecha_actualizacion") != hoy]
    if args.limit:
        ids = ids[: args.limit]
    nuevos = {i for i in ids if i not in cache}
    print(f"{len(ids)} juego(s) ({len(nuevos)} sin datos todavía), {len(fields)} campo(s): {', '.join(fields)}", flush=True)

    # Por tandas: cada una se guarda apenas termina, así un corte (red, BGG)
    # no pierde lo ya traído — y con --skip-fresh se retoma donde quedó.
    updated_total, changes, con_cambios, no_devueltos = 0, 0, 0, 0
    deltas = {"Board Game Rank": [], "usersrated": [], "average": []}  # nuevo - viejo, para el control del log
    fetched_nuevos = {}
    for start in range(0, len(ids), CHUNK_SIZE):
        chunk = ids[start:start + CHUNK_SIZE]
        try:
            fetched = fetch_things(chunk, marketplace="marketplacelistings" in fields or bool(nuevos & set(chunk)))
        except Exception as e:  # noqa: BLE001 — se corta, pero lo ya guardado queda
            print(f"\nSe cortó en el juego {start + 1} de {len(ids)}: {e}. Lo anterior ya está guardado; "
                  "retomar con --skip-fresh.", file=sys.stderr)
            break
        updates = {}
        mios = {r["bgg_id"] for r in collection}
        faltan = [i for i in chunk if i not in fetched]
        dudosos = set()  # la confirmación falló por un error (red, BGG): no es lo mismo que "BGG no lo devuelve"
        if faltan:  # se confirma uno por uno: que falte dentro de un lote no alcanza para darlo por muerto
            for i in faltan:
                time.sleep(5)
                try:
                    fetched.update(fetch_things([i]))
                except Exception:  # noqa: BLE001
                    dudosos.add(i)
        for bgg_id in chunk:
            attrs = fetched.get(bgg_id)
            if attrs is None:
                no_devueltos += 1
                if bgg_id in dudosos:
                    print(f"  bgg_id={bgg_id}: no pude confirmarlo (error de red/BGG), no se toca.", file=sys.stderr)
                elif bgg_id in mios:
                    print(f"  bgg_id={bgg_id}: BGG no lo devolvió, pero está en TU colección: no se toca.", file=sys.stderr)
                elif not args.dry_run and bgg_id in cache:
                    move_to_watch([bgg_id], hoy)
                    print(f"  bgg_id={bgg_id} ({cache[bgg_id].get('name')}): BGG no lo devuelve; pasa a vigilancia y sale del catálogo.", file=sys.stderr)
                else:
                    print(f"  bgg_id={bgg_id}: BGG no lo devolvió, no se toca.", file=sys.stderr)
                continue
            row_updates = {"fecha_actualizacion": hoy}
            for field in (ALL_FIELDS if bgg_id in nuevos else fields):
                new, old = attrs.get(field), cache.get(bgg_id, {}).get(field)
                if new in (None, "", []):
                    continue  # nunca borrar un dato ya cargado con un vacío
                if new != old:
                    row_updates[field] = new
                    changes += 1
                    if field in deltas and old not in (None, ""):
                        try:
                            deltas[field].append(float(new) - float(old))
                        except ValueError:
                            pass
                    if changes <= 40:
                        print(f"  {bgg_id} {field}: {str(old)[:40]!r} -> {str(new)[:40]!r}")
            updates[bgg_id] = row_updates
            if bgg_id in nuevos:
                fetched_nuevos[bgg_id] = attrs
            con_cambios += len(row_updates) > 1
        if updates and not args.dry_run:
            upsert_bgg_cache(updates)
        updated_total += len(updates)
        print(f"  {min(start + CHUNK_SIZE, len(ids))}/{len(ids)} guardados", flush=True)

    resolve_cazagangas({i: a for i, a in fetched_nuevos.items()}, args.dry_run)
    print(f"{changes} cambio(s) en {con_cambios} juego(s), {updated_total} con fecha_actualizacion al día"
          + (" (dry-run, no se escribió nada)" if args.dry_run else ""))
    if updated_total and not args.dry_run:
        write_logs_actualizacion_data("BGG", "API xmlapi2 (con token)", len(load_bgg_cache()), updated_total, time.time() - inicio,
                          resumen_control(con_cambios, updated_total, deltas), args.motivo, args.nota)
        print(f"OK: datos en {BGG_DATA_PATH.name}, colección en {COLLECTION_PATH.name}, registro en {LOG_PATH}")


if __name__ == "__main__":
    main()
