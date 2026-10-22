# 05 — Deployment

El "deployment" acá es GitHub Pages sirviendo el repo directo:

- Sitio en vivo: https://nachomondino1.github.io/boardgame/
- Config de Pages: **Deploy from branch** `main`, carpeta `/docs`. GitHub Pages con este modo solo admite `/` o `/docs` como carpeta (no una carpeta custom como `05_deployment/`) — por eso el sitio real (`index.html`, `hoy.html`, `comprar.html`, `css/`, `js/`, `data/`) vive en `../docs/`, y esta carpeta queda como documentación del paso de deploy, no como el sitio en sí.
- `../.github/workflows/sync-sheet.yml` es el único paso de "build": regenera `../docs/data/data.json` y pushea a `main`, lo que dispara el redeploy automático de Pages.

Si en algún momento hace falta publicar una carpeta que no sea `/` ni `/docs`, hay que pasar la config de Pages a deploy por GitHub Actions (`actions/upload-pages-artifact` + `actions/deploy-pages`), que sí permite publicar una carpeta arbitraria.
