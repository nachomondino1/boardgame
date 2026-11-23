// GET /api/notas?user=<usuario de BGG>
// Notas personales del autor. Viven en el servidor, no en el repo (que es público): el KV `NOTAS`
// (clave "notas": el mismo JSON que genera build_catalog.py en docs/data/notas.json, se sube con
// scripts/subir_notas.sh) y el secreto NOTAS_USER (el usuario de BGG del autor). Solo si `user` coincide con NOTAS_USER devuelve las notas;
// para cualquier otro, {} (igual que cuando no hay notas: no revela que existen).
// Es una primera versión: el usuario de BGG es público, así que esto NO es autenticación,
// solo evita mostrarle tus notas a quien no pone tu usuario.

function json(body) {
  return new Response(body, {
    headers: { "Content-Type": "application/json; charset=utf-8", "Cache-Control": "private, no-store" },
  });
}

export async function onRequestGet({ request, env }) {
  const user = (new URL(request.url).searchParams.get("user") || "").trim().toLowerCase();
  const autor = ((env && env.NOTAS_USER) || "").trim().toLowerCase();
  if (!user || !autor || user !== autor || !env.NOTAS) return json("{}");
  return json((await env.NOTAS.get("notas")) || "{}");
}
