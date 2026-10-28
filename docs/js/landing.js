// Landing (index.html): nav + números de la colección a partir de data.json.
// Si el fetch falla, los stats quedan ocultos y el resto de la página sigue funcionando.
document.getElementById("nav").innerHTML = navTemplate("index.html");

loadGames()
  .then((games) => {
    const own = games.filter((g) => g.estado === "Own").length;
    const watch = games.filter((g) => g.estado === "Want to buy").length;
    const ranks = games.filter((g) => g.estado === "Own" && g.ranking_bgg != null).map((g) => g.ranking_bgg);
    document.getElementById("stat-own").textContent = own;
    document.getElementById("stat-watch").textContent = watch;
    document.getElementById("stat-top").textContent = ranks.length ? `#${Math.min(...ranks).toLocaleString("es-AR")}` : "–";
    document.getElementById("stats").hidden = false;
  })
  .catch(() => {});
