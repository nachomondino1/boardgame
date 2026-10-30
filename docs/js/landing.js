// Landing (index.html): nav y "Cargá tus juegos". Los números de la colección
// viven en Mi ludoteca; acá el panel solo guarda la colección en el navegador.
document.getElementById("nav").innerHTML = navTemplate("index.html");

mountCollectionLoader(document.getElementById("collection-loader"), { onChange: () => {} });
