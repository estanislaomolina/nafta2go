'use strict';
const form = document.querySelector('#operation-form'), access = document.querySelector('#operation-access');
const source = document.querySelector('#operation-source'), submit = document.querySelector('#operation-submit');
const status = document.querySelector('#operation-status'), error = document.querySelector('#operation-error');
const results = document.querySelector('#operation-results');
let controller, generation = 0;
function node(tag, text) { const element = document.createElement(tag); element.textContent = text; return element; }
function details(values) {
  const list = document.createElement('dl');
  for (const [label, value] of values) list.append(node('dt', label), node('dd', value ?? 'Sin datos'));
  return list;
}
function card(title, values) { const element = document.createElement('article'); element.append(node('h3', title), details(values)); return element; }
function run(title, data) {
  if (!data) { const element = document.createElement('article'); element.append(node('h3', title), node('p', 'No hay una ejecución registrada.')); return element; }
  const states = {succeeded: 'Exitosa', failed: 'Fallida', running: 'En ejecución'};
  return card(title, [
    ['Ejecución', data.id], ['Estado', states[data.status] ?? 'Sin datos'],
    ['Inicio (UTC)', data.started_at], ['Fin (UTC)', data.finished_at],
    ['Duración (s)', data.duration_seconds], ['Reglas', data.rules_version],
    ['Filas normalizadas', data.price_rows], ['Estaciones distintas', data.stations],
    ['Filas rechazadas', data.rejected_rows], ['SHA-256', data.sha256], ['Captura (bytes)', data.size_bytes]
  ]);
}
function render(metrics, ingestion) {
  const queries = metrics.queries, routes = metrics.routes;
  results.append(node('p', 'Lectura de ingesta: ' + ingestion.observed_at + ' (UTC).'));
  results.append(card('Consultas HTTP · proceso actual', [
    ['Consultas terminadas', queries.completed], ['Duración acumulada (ms)', queries.duration_ms_total],
    ['Con recomendación', queries.outcome.recommended ?? 0], ['Sin alternativas', queries.outcome.no_feasible_stations ?? 0],
    ['Sin cobertura', queries.outcome.insufficient_coverage ?? 0], ['Con error HTTP', queries.outcome.http_error ?? 0]
  ]));
  results.append(card('Rutas · caché del proceso', [
    ['Reutilizaciones', routes.hits], ['Faltantes en caché', routes.misses], ['Solicitudes al proveedor', routes.requests],
    ['Errores del proveedor', routes.errors], ['Bloqueos por cupo', routes.limited], ['Proveedor ocupado', routes.busy], ['Entradas', routes.entries]
  ]));
  const notice = node('p', 'Los contadores no incluyen la CLI y las rutas grabadas no usan esta caché.'); notice.className = 'hint'; results.append(notice);
  results.append(node('h3', ingestion.status === 'alerting' ? 'Condiciones de alerta' : 'Sin condiciones de alerta'));
  const conditions = document.createElement('ul');
  const kinds = {missing: 'Falta el intento diario esperado', failed: 'La última ejecución terminada falló', stalled: 'Una ejecución lleva al menos dos horas'};
  for (const condition of ingestion.conditions) conditions.append(node('li', (kinds[condition.kind] ?? 'Condición no reconocida') + (condition.run_id == null ? '' : ' · ejecución ' + condition.run_id)));
  results.append(conditions);
  if (ingestion.conditions_truncated) results.append(node('p', 'Se muestran ' + ingestion.conditions.length + ' de ' + ingestion.condition_count + ' condiciones.'));
  results.append(run('Último intento', ingestion.latest_attempt), run('Última ingesta exitosa', ingestion.latest_successful));
  const limit = node('p', 'Esta lectura recalcula condiciones; no crea ni resuelve alertas del monitor. Sin alertas no significa que los precios sean actuales. Histórico usa las mismas reglas, aunque no tenga una tarea diaria programada.');
  limit.className = 'notice warning'; results.append(limit);
}
function clear() {
  generation++; controller?.abort(); access.value = ''; results.replaceChildren(); error.hidden = true;
  source.disabled = false; submit.disabled = false; status.textContent = 'Acceso y datos limpiados.';
}
document.querySelector('#operation-clear').addEventListener('click', () => { clear(); access.focus(); });
window.addEventListener('pagehide', clear);
form.addEventListener('submit', async event => {
  event.preventDefault(); if (!form.reportValidity()) return;
  const current = ++generation, selected = source.value;
  controller?.abort(); controller = new AbortController(); const requestController = controller, signal = controller.signal;
  const timer = setTimeout(() => requestController.abort(), 15000);
  results.replaceChildren(); error.hidden = true; submit.disabled = true; source.disabled = true;
  status.textContent = 'Consultando estado…';
  async function read(url) {
    const response = await fetch(url, {signal, cache: 'no-store', credentials: 'omit', redirect: 'error', headers: {Authorization: 'Bearer ' + access.value.trim()}});
    if (!response.ok) throw new Error(response.status === 401 ? 'unauthorized' : 'unavailable');
    return response.json();
  }
  try {
    const [metrics, ingestion] = await Promise.all([read('/api/v1/operations'), read('/api/v1/operations/ingestion?source=' + encodeURIComponent(selected))]);
    if (current !== generation) return;
    render(metrics, ingestion); status.textContent = 'Estado actualizado. Fuente: ' + (selected === 'vigente' ? 'precios vigentes.' : 'histórico.'); results.focus();
  } catch (failure) {
    if (current !== generation) return;
    results.replaceChildren(); status.textContent = 'No se obtuvo una lectura completa.';
    error.textContent = failure.message === 'unauthorized' ? 'El código de acceso no es válido.' : failure.name === 'AbortError' ? 'La lectura demoró demasiado. Volvé a intentar.' : 'No se pudo leer el estado. Revisá la conexión y la disponibilidad del servicio.';
    error.hidden = false; error.focus();
  } finally {
    clearTimeout(timer); requestController.abort(); if (current === generation) { submit.disabled = false; source.disabled = false; }
  }
});
submit.disabled = false;
