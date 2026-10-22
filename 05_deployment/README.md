# 05 — Deployment

El "deployment" acá es GitHub Pages sirviendo el repo directo:

- Sitio en vivo: https://nachomondino1.github.io/boardgame/
- Config de Pages: **Deploy from branch** `main`, carpeta `/` (raíz). GitHub Pages con este modo **solo admite `/` o `/docs` como carpeta** — no una carpeta custom — así que `index.html`, `hoy.html`, `comprar.html`, `css/`, `js/` y `data/data.json` se quedan en la raíz del repo en vez de vivir acá adentro.
- `../.github/workflows/sync-sheet.yml` es el único paso de "build": regenera `data/data.json` y pushea a `main`, lo que dispara el redeploy automático de Pages.

Si en algún momento se quiere mover el sitio de verdad a esta carpeta, hay que pasar la config de Pages a deploy por GitHub Actions (`actions/upload-pages-artifact` + `actions/deploy-pages`), que sí permite publicar una carpeta arbitraria.
