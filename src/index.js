// Entrada del Worker en Cloudflare (flujo "Workers" con archivos estáticos, ver
// wrangler.jsonc): /api/collection y las de cuenta (account.js) las atienden funciones; el resto son los
// archivos de docs/, que Cloudflare sirve solo y no pasan por acá.
import { onRequestGet } from "../functions/api/collection.js";
import { handleAccount } from "../functions/api/account.js";

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (url.pathname === "/api/collection" && request.method === "GET") {
      return onRequestGet({ request, env });
    }
    const account = await handleAccount(request, env);
    if (account) return account;
    return env.ASSETS.fetch(request);
  },
};
