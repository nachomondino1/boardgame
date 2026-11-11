// Landing (index.html): nav, "Cargá tus juegos" y el paso siguiente.
// Con juegos cargados, el CTA del hero y un bloque debajo del panel llevan a ¿Qué jugamos hoy?.
document.getElementById("nav").innerHTML = navTemplate("index.html");

function actualizarSiguiente() {
  const own = Object.values(loadCollection().games).filter((g) => g.own).length;
  const siguiente = document.getElementById("siguiente");
  const cta = document.getElementById("hero-cta");
  siguiente.hidden = own === 0;
  document.getElementById("siguiente-texto").textContent =
    `Listo: tenés ${own} juego${own === 1 ? "" : "s"} cargado${own === 1 ? "" : "s"}. Ahora decinos cuántos son.`;
  cta.textContent = own ? "Elegir qué jugar" : "Cargá tus juegos";
  cta.href = own ? "hoy.html" : "#cargar";
}

mountCollectionLoader(document.getElementById("collection-loader"), { onChange: actualizarSiguiente });
actualizarSiguiente();
