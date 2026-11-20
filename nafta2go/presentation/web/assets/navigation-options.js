"use strict";
// Sólo crea enlaces locales: no consulta proveedores ni guarda el recorrido.
function navigationOptions(link, trip) {
  function coordinate(value) {
    return value && typeof value.lat === 'number' && typeof value.lon === 'number'
      && Number.isFinite(value.lat) && Number.isFinite(value.lon)
      && value.lat >= -34.71 && value.lat <= -34.52 && value.lon >= -58.54 && value.lon <= -58.33
      ? value.lat + ',' + value.lon : null;
  }
  if (!link || typeof link.url !== 'string' || typeof link.label !== 'string') return null;
  let supplied;
  try { supplied = new URL(link.url); } catch { return null; }
  if (supplied.origin !== 'https://www.google.com' || supplied.pathname !== '/maps/dir/') return null;
  const pieces = (supplied.searchParams.get('destination') || '').split(',');
  if (pieces.length !== 2 || pieces.some(value => !value.trim())) return null;
  const station = coordinate({lat: Number(pieces[0]), lon: Number(pieces[1])});
  if (!station) return null;
  function anchor(label, url, className) {
    const a = document.createElement('a'); a.textContent = label + ' ↗'; a.href = url.href;
    a.className = className; a.target = '_blank'; a.rel = 'noopener noreferrer';
    return a;
  }
  const section = document.createElement('div'); section.className = 'navigation-options';
  const stationMap = new URL('https://www.google.com/maps/dir/');
  stationMap.search = new URLSearchParams({api: '1', destination: station, travelmode: 'driving', dir_action: 'navigate'});
  const main = anchor(link.label, stationMap, 'navigate');
  main.setAttribute('aria-label', link.label + '. Google Maps, nueva pestaña'); section.append(main);
  const details = document.createElement('details'), summary = document.createElement('summary');
  details.className = 'navigation-choices'; summary.textContent = 'Mapa del viaje y Waze'; details.append(summary);
  const origin = coordinate(trip?.origin), destination = coordinate(trip?.destination ?? trip?.origin);
  if (origin && destination) {
    const map = new URL('https://www.google.com/maps/dir/');
    map.search = new URLSearchParams({api: '1', origin, destination, waypoints: station, travelmode: 'driving'});
    const privateTrip = document.createElement('div'); privateTrip.className = 'private-trip';
    privateTrip.append(anchor('Ver viaje por la estación en Google Maps', map, 'trip-map'));
    const privacy = document.createElement('p'); privacy.className = 'hint';
    privacy.textContent = 'Al abrir el viaje, Google Maps recibe el origen, la estación y el destino de esta consulta. Recalcula la ruta; verificá que incluya la parada.';
    privateTrip.append(privacy); details.append(privateTrip);
  }
  const waze = new URL('https://waze.com/ul');
  waze.search = new URLSearchParams({ll: station, navigate: 'yes', utm_source: 'nafta2go'});
  details.append(anchor('Ir a la estación con Waze', waze, 'waze-map'));
  const notice = document.createElement('p'); notice.className = 'hint';
  notice.textContent = 'Waze navega hasta la estación desde la ubicación de su aplicación. El destino final del viaje se configura aparte. Las rutas externas pueden diferir de la recomendación.';
  details.append(notice); section.append(details); return section;
}

window.addEventListener('pagehide', () => { for (const element of document.querySelectorAll('.private-trip')) element.remove(); });
