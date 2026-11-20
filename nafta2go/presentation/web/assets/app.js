"use strict";
class QueryError extends Error {}
const form = document.querySelector("#query"), output = document.querySelector("#results");
const status = document.querySelector("#status"), error = document.querySelector("#error");
const submit = document.querySelector("#submit"), access = document.querySelector("#access");
const back = document.querySelector("#return"), destination = document.querySelector("#destination");
const priorities = {combustible_neto: "Más combustible neto", menor_desvio: "Menor desvío", equilibrio: "Equilibrio"};
const reasons = {route_unavailable: "Ruta no disponible", station_unreachable: "No alcanza el combustible para llegar", reserve_at_station: "Llegar compromete la reserva", no_budget: "Presupuesto insuficiente", no_tank_space: "El tanque no tiene espacio", insufficient_fuel_for_trip: "No alcanza el combustible para completar el viaje con reserva"};
function node(tag, text, className = "") {
  const item = document.createElement(tag);
  item.textContent = text; item.className = className; return item;
}
function number(value, unit = "") {
  return value == null ? "Sin dato" : new Intl.NumberFormat("es-AR", {maximumFractionDigits: 2}).format(Number(value)) + unit;
}
function minutes(value) {
  return value == null ? "Sin dato" : "~" + new Intl.NumberFormat("es-AR").format(Math.ceil(Number(value)) || 0) + " min";
}
function date(value) {
  return new Intl.DateTimeFormat("es-AR", {dateStyle: "short", timeStyle: "short", hour12: false, timeZone: "America/Argentina/Buenos_Aires"}).format(new Date(value));
}
const referenceRequests = new Set();
let referenceGeneration = 0;
function clearReferences() {
  referenceGeneration++; for (const request of referenceRequests) request.abort(); referenceRequests.clear();
  for (const button of output.querySelectorAll('.price-reference-button')) button.disabled = false;
  for (const result of output.querySelectorAll('.price-reference-result')) { result.replaceChildren(); result.removeAttribute('aria-busy'); }
}
function priceReference(data, row) {
  const section = document.createElement('section'), button = node('button', 'Consultar referencia de precio', 'secondary price-reference-button');
  button.type = 'button'; button.setAttribute('aria-label', 'Consultar referencia de precio de ' + (row.brand || 'estación ' + row.station_id) + ' ' + (row.address || ''));
  const result = node('div', '', 'price-reference-result'); result.setAttribute('role', 'status'); result.tabIndex = -1;
  const product = {super: 2, premium: 3}[data.query.fuel_type], schedule = data.query.schedule_id;
  button.addEventListener('click', async () => {
    const generation = referenceGeneration;
    const controller = new AbortController(); referenceRequests.add(controller);
    const timer = setTimeout(() => controller.abort(), 15000);
    result.replaceChildren(node('p', 'Consultando referencia…')); result.setAttribute('aria-busy', 'true'); button.disabled = true;
    try {
      const response = await fetch('/api/v1/price-diagnostics/' + encodeURIComponent(row.station_id) + '?product_id=' + product + '&schedule_id=' + schedule,
        {signal: controller.signal, credentials: 'omit', redirect: 'error', cache: 'no-store', referrerPolicy: 'no-referrer', headers: {Authorization: 'Bearer ' + access.value.trim()}});
      if (!response.ok) throw new QueryError(response.status === 401 ? 'Revisá el código de acceso para consultar la referencia.' : response.status === 404 ? 'No encontramos esa publicación. Volvé a buscar estaciones.' : 'La referencia no está disponible por ahora. El precio publicado conserva su valor y fecha.');
      const value = await response.json();
      if (generation !== referenceGeneration || !result.isConnected) return;
      const publication = Date.parse(row.published_at_local + '-03:00');
      if (value.scope !== 'published_price_retrospective' || value.data_run_id !== data.data_run_id || String(value.station_id) !== String(row.station_id) || value.product_id !== product || value.schedule_id !== schedule || Number(value.official_price_ars_per_l) !== Number(row.price_ars_per_l) || Date.parse(value.published_at) !== publication)
        throw new QueryError('La publicación cambió o no coincide con esta recomendación. Volvé a buscar estaciones.');
      if (value.status === 'unavailable') throw new QueryError('No hay suficiente historia comparable para esta publicación. No se emite una alerta.');
      if (value.status !== 'reference_only' || value.alert_level !== 'not_calibrated' || value.reference_ars_per_l == null || !Number.isFinite(Number(value.reference_ars_per_l)) || Number(value.reference_ars_per_l) <= 0 || value.difference_ars_per_l == null || !Number.isFinite(Number(value.difference_ars_per_l)))
        throw new QueryError('No pudimos obtener una referencia válida para esta publicación.');
      result.replaceChildren(node('h4', 'Referencia histórica de esta publicación'));
      const details = document.createElement('dl');
      for (const [label, text] of [['Referencia', number(value.reference_ars_per_l, ' ARS/L')], ['Diferencia: publicado menos referencia', number(value.difference_ars_per_l, ' ARS/L')]]) details.append(node('dt', label), node('dd', text));
      result.append(details, node('p', 'Corresponde a la publicación del ' + date(value.published_at) + '. No estima el precio actual ni demuestra que el precio publicado sea incorrecto.', 'hint'), node('p', 'Todavía no hay una alerta validada para esta comparación.', 'notice warning'));
      const trace = document.createElement('details'); trace.append(node('summary', 'Detalles de la referencia'));
      const methods = {mediana_previa: 'Mediana comparable previa', ultimo_precio: 'Último precio publicado de la estación', bandera_reciente: 'Mediana reciente de la bandera'};
      trace.append(node('p', (methods[value.method] || 'Referencia histórica') + ' · Versión: ' + value.version, 'source')); result.append(trace);
    } catch (failure) {
      if (generation !== referenceGeneration || !result.isConnected) return;
      result.replaceChildren(node('p', failure.name === 'AbortError' ? 'La referencia demoró demasiado. Podés volver a intentar.' : failure instanceof QueryError ? failure.message : 'No pudimos consultar la referencia. Revisá la conexión e intentá más tarde.', 'notice warning'));
    } finally {
      clearTimeout(timer); referenceRequests.delete(controller);
      if (generation === referenceGeneration && result.isConnected) { result.removeAttribute('aria-busy'); button.disabled = false; result.focus(); }
    }
  });
  section.append(button, result); return section;
}
function mapsLink(link) {
  if (!link || typeof link.url !== "string" || typeof link.label !== "string") return null;
  let url; try { url = new URL(link.url); } catch { return null; }
  if (url.origin !== "https://www.google.com" || url.pathname !== "/maps/dir/") return null;
  const anchor = node("a", link.label + " ↗", "navigate");
  anchor.href = url.href; anchor.target = "_blank"; anchor.rel = "noopener noreferrer";
  anchor.setAttribute("aria-label", link.label + ". Google Maps, nueva pestaña"); return anchor;
}
function day(value) {
  return value.replace(/^(\d{4})-(\d{2})-(\d{2})T.*/, "$3/$2/$1");
}
function staleEstimates(block) {
  const finite = value => value != null && Number.isFinite(Number(value)) && Number(value) > 0;
  const stamp = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}/;
  const items = (block && block.status === "available" && Array.isArray(block.items) ? block.items : [])
    .filter(item => finite(item.official_price_ars_per_l) && finite(item.estimate_ars_per_l) && finite(item.official_age_days)
      && [item.official_published_at_local, item.reference_from_local, item.reference_to_local].every(value => stamp.test(String(value))));
  if (!items.length) return null;
  const section = document.createElement("section"), title = node("h3", "Estaciones con precio desactualizado");
  title.id = "stale-title"; section.setAttribute("aria-labelledby", "stale-title"); section.className = "stale-estimates";
  section.append(title, node("p", "No participan de la recomendación: su último precio oficial tiene más de " + block.min_age_days + " días. " + block.notice, "notice warning"));
  for (const item of items) {
    const card = document.createElement("article"), detail = document.createElement("dl");
    card.append(node("p", "ESTIMADO", "badge"), node("h4", item.brand || item.company || "Estación " + item.station_id), node("p", item.address || "Dirección no informada", "address"));
    for (const [label, value] of [
      ["Precio oficial", number(item.official_price_ars_per_l, " ARS/L") + " · publicado el " + day(item.official_published_at_local) + " (hace " + number(item.official_age_days) + " días)"],
      ["Precio estimado", number(item.estimate_ars_per_l, " ARS/L")],
      ["Referencia", "Mediana de " + item.reference_count + " precios de la misma bandera entre el " + day(item.reference_from_local) + " y el " + day(item.reference_to_local)],
    ]) detail.append(node("dt", label), node("dd", value));
    card.append(detail);
    const anchor = mapsLink(item.navigation); if (anchor) card.append(anchor);
    section.append(card);
  }
  return section;
}
function show(data) {
  output.replaceChildren();
  output.append(node("p", "Vigencia máxima aplicada: " + data.query.max_price_age_days + " días respecto de la referencia de precios.", "hint"));
  if (data.status === "historical_scenario") output.append(node("p", "ESCENARIO HISTÓRICO · Precios del " + date(data.scenario.reference_at) + ". No son precios actuales.", "notice warning"));
  if (data.outcome !== "recommended") {
    const missing = data.outcome === "insufficient_coverage";
    output.append(node("h3", missing ? "No hay cobertura suficiente" : "No encontramos una opción viable"));
    output.append(node("p", missing ? "Faltan estaciones con datos recientes para este recorrido. Probá otro recorrido o consultá más tarde." : "Revisá tu presupuesto, combustible disponible y reserva. Los motivos aparecen debajo."));
  }
  const rows = new Map(data.evaluations.map(row => [row.station_id, row]));
  const links = new Map(data.navigation.map(link => [link.station_id, link]));
  for (const choice of data.alternatives) {
    const row = rows.get(choice.station_id), metrics = row.metrics, card = document.createElement("article");
    card.append(node("p", choice.priorities.map(key => priorities[key] || key).join(" · "), "priorities"));
    card.append(node("h3", row.brand || row.company || "Estación " + row.station_id), node("p", row.address, "address"));
    const summary = document.createElement("dl"); summary.className = "key-figures";
    for (const [label, value] of [
      ["Precio", number(row.price_ars_per_l, " ARS/L")], ["Costo de la carga", number(metrics.cost_ars, " ARS")],
      ["Litros a cargar", number(metrics.purchased_l, " L")], ["Desvío", "+" + number(metrics.extra_km, " km") + " · " + minutes(metrics.extra_min)],
    ]) { const item = document.createElement("div"); item.append(node("dt", label), node("dd", value)); summary.append(item); }
    card.append(summary);
    const more = document.createElement("details"), detail = document.createElement("dl");
    more.className = "card-detail"; more.append(node("summary", "Ver detalle del cálculo"));
    for (const [label, value] of [
      ["Consumo del recorrido", number(metrics.total_consumption_l, " L")], ["Ganancia neta", number(metrics.net_gain_l, " L")],
      ["Combustible al finalizar", number(metrics.final_l, " L")], ["Reserva exigida", number(data.query.reserve_l, " L")],
      ["Autonomía final", number(metrics.final_range_km, " km")],
    ]) detail.append(node("dt", label), node("dd", value));
    more.append(detail, node("p", "Publicado (hora Argentina): " + row.published_at_local.replace(/^(\d{4})-(\d{2})-(\d{2})T(\d{2}:\d{2}).*/, "$3/$2/$1 $4"), "hint"));
    if (row.alerts.length) card.append(node("p", "Este dato tiene advertencias de calidad. Revisá su fuente y vigencia.", "notice warning"));
    if (data.status === 'ready' && data.data_run_id != null && {super: 2, premium: 3}[data.query.fuel_type] && [2, 3].includes(data.query.schedule_id)) more.append(priceReference(data, row));
    const anchor = mapsLink(links.get(choice.station_id)); if (anchor) card.append(anchor);
    card.append(more); output.append(card);
  }
  if (data.navigation_notice) output.append(node("p", data.navigation_notice, "hint"));
  const estimates = staleEstimates(data.stale_price_estimates);
  if (estimates) output.append(estimates);
  const discarded = data.evaluations.filter(row => !row.feasible);
  if (discarded.length || Object.keys(data.exclusions).length) {
    const details = document.createElement("details"), list = document.createElement("ul");
    details.append(node("summary", "Por qué se descartaron estaciones"));
    for (const row of discarded) list.append(node("li", (row.brand || "Estación " + row.station_id) + " · " + (row.address || "Dirección no informada") + ": " + row.reasons.map(key => reasons[key] || key).join("; ")));
    if (Object.keys(data.exclusions).length) list.append(node("li", "También se excluyeron datos que no cumplen ubicación, producto, horario o vigencia: " + Object.values(data.exclusions).reduce((a, b) => a + b, 0)));
    details.append(list); output.append(details);
  }
  output.append(node("p", "Fuente: " + data.source.name + " · " + data.source.license + ". Referencia de precios: " + date(data.price_reference_at), "source"));
  status.textContent = data.alternatives.length ? data.alternatives.length === 1 ? "Encontramos una alternativa." : "Encontramos " + data.alternatives.length + " alternativas." : "Consulta terminada sin alternativas.";
  output.focus();
}
form.addEventListener("input", () => { for (const input of form.querySelectorAll("input")) input.setCustomValidity(""); });
form.addEventListener("submit", async event => {
  event.preventDefault();
  for (const input of form.querySelectorAll("input")) input.setCustomValidity("");
  for (const key of ["consumption_l_per_100km", "tank_capacity_l"]) if (Number(form.elements[key].value) <= 0) form.elements[key].setCustomValidity("Ingresá un valor mayor que cero.");
  for (const key of ["remaining_l", "reserve_l"]) if (Number(form.elements[key].value) > Number(form.elements.tank_capacity_l.value)) form.elements[key].setCustomValidity("No puede superar la capacidad del tanque.");
  if (!access.value.trim()) access.setCustomValidity("Ingresá el código de acceso.");
  if (!form.reportValidity()) return;
  const data = new FormData(form), body = {};
  for (const key of ["consumption_l_per_100km", "tank_capacity_l", "remaining_l", "reserve_l", "budget_ars", "fuel_type"]) body[key] = data.get(key);
  body.origin = {lat: Number(data.get("origin_lat")), lon: Number(data.get("origin_lon"))};
  body.destination = back.checked ? null : {lat: Number(data.get("destination_lat")), lon: Number(data.get("destination_lon"))};
  body.schedule_id = Number(data.get("schedule_id"));
  const fields = [...form.querySelectorAll("fieldset")], disabled = fields.map(field => field.disabled);
  fields.forEach(field => field.disabled = true);
  clearReferences();
  error.hidden = true; error.textContent = ""; output.replaceChildren(); output.setAttribute("aria-busy", "true");
  status.textContent = "Buscando estaciones…"; submit.disabled = true; submit.textContent = "Buscando…";
  const controller = new AbortController(), timer = setTimeout(() => controller.abort(), 60000);
  try {
    const response = await fetch("/api/v1/recommendations", {method: "POST", credentials: "omit", redirect: "error", cache: "no-store", referrerPolicy: "no-referrer", signal: controller.signal,
      headers: {"Content-Type": "application/json", Authorization: "Bearer " + access.value.trim()}, body: JSON.stringify(body)});
    const result = await response.json();
    if (!response.ok) {
      const messages = {unauthorized: "El código de acceso no es válido. Revisalo e intentá de nuevo.", invalid_request: "Revisá los datos del vehículo y las coordenadas: el recorrido debe estar dentro de CABA.", routes_quota_exceeded: "Se alcanzó el límite del servicio de rutas. Volvé a intentar más tarde.", routes_timeout: "El servicio de rutas demoró demasiado. Volvé a intentar más tarde."};
      throw new QueryError(messages[result.detail?.code] || "No pudimos completar la consulta. El servicio no está disponible; intentá más tarde.");
    }
    show(result);
  } catch (failure) {
    output.replaceChildren(); error.hidden = false;
    error.textContent = failure.name === "AbortError" ? "La consulta demoró demasiado. Volvé a intentar más tarde." : failure instanceof QueryError ? failure.message : "No pudimos obtener una respuesta válida. Revisá tu conexión e intentá más tarde.";
    status.textContent = "Consulta no completada."; error.focus();
  } finally {
    clearTimeout(timer); fields.forEach((field, index) => field.disabled = disabled[index]);
    output.removeAttribute("aria-busy"); submit.disabled = false; submit.textContent = "Comparar estaciones";
  }
});
window.addEventListener("pagehide", () => { access.value = ""; clearReferences(); });
submit.disabled = false;
