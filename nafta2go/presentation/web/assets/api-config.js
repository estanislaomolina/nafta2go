"use strict";
// El destino se fija al publicar la web; nunca se toma de búsquedas ni parámetros.
function apiUrl(path) {
  const configured = document.querySelector('meta[name="nafta2go-api-origin"]');
  return new URL(path, configured && configured.content ? configured.content : window.location.origin).href;
}
