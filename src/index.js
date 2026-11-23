// Entrada del Worker en Cloudflare (flujo "Workers" con archivos estáticos, ver
// wrangler.jsonc): /api/collection lo atiende la función; el resto son los
// archivos de docs/, que Cloudflare sirve solo y no pasan por acá.
import { onRequestGet } from "../functions/api/collection.js";

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (url.pathname === "/api/collection" && request.method === "GET") {
      return onRequestGet({ request, env });
    }
    return env.ASSETS.fetch(request);
  },
};
