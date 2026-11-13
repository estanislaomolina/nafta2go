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
  return value == null ? "Sin dato" : new Intl.NumberFormat("es-AR", {maximumFractionDigits: 3}).format(Number(value)) + unit;
}
function date(value) {
  return new Intl.DateTimeFormat("es-AR", {dateStyle: "short", timeStyle: "short", hour12: false, timeZone: "America/Argentina/Buenos_Aires"}).format(new Date(value));
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
    const values = [
      ["Precio publicado", number(row.price_ars_per_l, " ARS/L")], ["Combustible a comprar", number(metrics.purchased_l, " L")],
      ["Costo de la carga", number(metrics.cost_ars, " ARS")], ["Consumo del recorrido", number(metrics.total_consumption_l, " L")],
      ["Ganancia neta", number(metrics.net_gain_l, " L")], ["Combustible al finalizar", number(metrics.final_l, " L")],
      ["Reserva exigida", number(data.query.reserve_l, " L")], ["Autonomía final", number(metrics.final_range_km, " km")],
      ["Desvío adicional", number(metrics.extra_km, " km") + " / " + number(metrics.extra_min, " min")],
    ];
    const detail = document.createElement("dl");
    for (const [label, value] of values) detail.append(node("dt", label), node("dd", value));
    card.append(detail, node("p", "Publicado (hora Argentina): " + row.published_at_local.replace(/^(\d{4})-(\d{2})-(\d{2})T(\d{2}:\d{2}).*/, "$3/$2/$1 $4"), "hint"));
    if (row.alerts.length) card.append(node("p", "Este dato tiene advertencias de calidad. Revisá su fuente y vigencia.", "notice warning"));
    const link = links.get(choice.station_id);
    if (link) {
      const url = new URL(link.url);
      if (url.origin === "https://www.google.com" && url.pathname === "/maps/dir/") {
        const anchor = node("a", link.label + " ↗", "navigate");
        anchor.href = url.href; anchor.target = "_blank"; anchor.rel = "noopener noreferrer";
        anchor.setAttribute("aria-label", link.label + ". Google Maps, nueva pestaña"); card.append(anchor);
      }
    }
    output.append(card);
  }
  if (data.navigation_notice) output.append(node("p", data.navigation_notice, "hint"));
  const discarded = data.evaluations.filter(row => !row.feasible);
  if (discarded.length || Object.keys(data.exclusions).length) {
    const details = document.createElement("details"), list = document.createElement("ul");
    details.append(node("summary", "Por qué se descartaron estaciones"));
    for (const row of discarded) list.append(node("li", (row.brand || "Estación " + row.station_id) + " · " + row.address + ": " + row.reasons.map(key => reasons[key] || key).join("; ")));
    if (Object.keys(data.exclusions).length) list.append(node("li", "También se excluyeron datos que no cumplen ubicación, producto, horario o vigencia: " + Object.values(data.exclusions).reduce((a, b) => a + b, 0)));
    details.append(list); output.append(details);
  }
  output.append(node("p", "Fuente: " + data.source.name + " · " + data.source.license + ". Referencia de precios: " + date(data.price_reference_at), "source"));
  status.textContent = data.alternatives.length ? data.alternatives.length === 1 ? "Encontramos una alternativa." : "Encontramos " + data.alternatives.length + " alternativas." : "Consulta terminada sin alternativas.";
  output.focus();
}
back.addEventListener("change", () => { destination.hidden = back.checked; destination.disabled = back.checked; });
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
document.querySelector("#locate").addEventListener("click", event => {
  const button = event.currentTarget, notice = document.querySelector("#location-status");
  if (!navigator.geolocation) { notice.textContent = "Este navegador no ofrece ubicación. Cargá las coordenadas manualmente."; return; }
  button.disabled = true; submit.disabled = true; notice.textContent = "Buscando tu ubicación…";
  navigator.geolocation.getCurrentPosition(position => {
    form.elements.origin_lat.value = position.coords.latitude; form.elements.origin_lon.value = position.coords.longitude;
    notice.textContent = "Ubicación completada. Confirmá que esté dentro de CABA."; button.disabled = false; submit.disabled = false;
  }, () => { notice.textContent = "No pudimos obtener tu ubicación. Cargá las coordenadas manualmente."; button.disabled = false; submit.disabled = false; }, {timeout: 10000, maximumAge: 0});
});
window.addEventListener("pagehide", () => access.value = "");
submit.disabled = false;
