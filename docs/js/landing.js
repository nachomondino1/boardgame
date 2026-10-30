// Landing (index.html): nav, "Cargá tus juegos" y números de la colección.
// Los números se actualizan cada vez que el visitante cambia su colección.
// Si el fetch de datos falla, los stats quedan ocultos y el resto de la página sigue funcionando.
document.getElementById("nav").innerHTML = navTemplate("index.html");

let GAMES = [];

function updateStats() {
  const own = GAMES.filter((g) => g.estado === "Own").length;
  const watch = GAMES.filter((g) => g.estado === "Want to buy").length;
  const ranks = GAMES.filter((g) => g.estado === "Own" && g.ranking_bgg != null).map((g) => g.ranking_bgg);
  document.getElementById("stat-own").textContent = own;
  document.getElementById("stat-watch").textContent = watch;
  document.getElementById("stat-top").textContent = ranks.length ? `#${Math.min(...ranks).toLocaleString("es-AR")}` : "–";
  // Sin juegos cargados los números no dicen nada: se ven recién cuando hay colección.
  document.getElementById("stats").hidden = own + watch === 0;
}

loadGames()
  .then((games) => {
    GAMES = games;
    updateStats();
  })
  .catch(() => {});

mountCollectionLoader(document.getElementById("collection-loader"), {
  onChange: () => {
    applyCollection(GAMES);
    updateStats();
  },
});
