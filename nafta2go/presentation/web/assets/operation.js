'use strict';
const form = document.querySelector('#operation-form'), access = document.querySelector('#operation-access');
const source = document.querySelector('#operation-source'), submit = document.querySelector('#operation-submit');
const status = document.querySelector('#operation-status'), error = document.querySelector('#operation-error');
const results = document.querySelector('#operation-results');
let controller, generation = 0;
function node(tag, text) { const element = document.createElement(tag); element.textContent = text; return element; }
const integer = new Intl.NumberFormat('es-AR', {maximumFractionDigits: 0}), decimal = new Intl.NumberFormat('es-AR', {maximumFractionDigits: 2});
function count(value) { return value == null ? 'Sin datos' : integer.format(Number(value)); }
function moment(value) {
  if (!value) return 'Sin datos';
  const parsed = new Date(value); if (Number.isNaN(parsed.getTime())) return 'Sin datos';
  return new Intl.DateTimeFormat('es-AR', {dateStyle: 'short', timeStyle: 'medium', hour12: false, timeZone: 'America/Argentina/Buenos_Aires'}).format(parsed);
}
function seconds(value) {
  if (value == null) return 'Sin datos';
  const total = Number(value);
  return total < 60 ? decimal.format(total) + ' s' : integer.format(Math.floor(total / 60)) + ' min ' + integer.format(Math.round(total % 60)) + ' s';
}
function milliseconds(value) {
  if (value == null) return 'Sin datos';
  const total = Number(value); return total < 1000 ? integer.format(Math.ceil(total)) + ' ms' : decimal.format(total / 1000) + ' s';
}
function bytes(value) {
  if (value == null) return 'Sin datos';
  const total = Number(value); return total < 1e6 ? decimal.format(total / 1e3) + ' kB' : decimal.format(total / 1e6) + ' MB';
}
function details(values) {
  const list = document.createElement('dl');
  for (const [label, value] of values) list.append(node('dt', label), node('dd', value ?? 'Sin datos'));
  return list;
}
function tiles(values) {
  const list = document.createElement('dl'); list.className = 'key-figures stats';
  for (const [label, value] of values) { const item = document.createElement('div'); item.append(node('dt', label), node('dd', value ?? 'Sin datos')); list.append(item); }
  return list;
}
function card(title, content) { const element = document.createElement('article'); element.append(node('h3', title), content); return element; }
function run(title, data) {
  if (!data) { const element = document.createElement('article'); element.append(node('h3', title), node('p', 'No hay una ejecución registrada.')); return element; }
  const states = {succeeded: 'Exitosa', failed: 'Fallida', running: 'En ejecución'};
  const element = card(title, tiles([
    ['Estado', states[data.status] ?? 'Sin datos'], ['Duración', seconds(data.duration_seconds)],
    ['Filas normalizadas', count(data.price_rows)], ['Estaciones', count(data.stations)],
  ]));
  const more = document.createElement('details'); more.className = 'card-detail';
  const hash = data.sha256 ? String(data.sha256) : null, digest = node('dd', hash ? hash.slice(0, 12) + '…' : 'Sin datos');
  if (hash) digest.title = hash;
  const list = details([
    ['Ejecución', count(data.id)], ['Inicio (hora Argentina)', moment(data.started_at)], ['Fin (hora Argentina)', moment(data.finished_at)],
    ['Filas rechazadas', count(data.rejected_rows)], ['Reglas', data.rules_version == null ? null : String(data.rules_version)], ['Captura', bytes(data.size_bytes)],
  ]);
  list.append(node('dt', 'SHA-256'), digest);
  more.append(node('summary', 'Ver detalle de la ejecución'), list); element.append(more);
  return element;
}
function render(metrics, ingestion) {
  const queries = metrics.queries, routes = metrics.routes;
  const alerting = ingestion.status === 'alerting', banner = document.createElement('div');
  banner.className = 'notice ' + (alerting ? 'warning' : 'ok');
  const heading = node('h3', alerting ? 'Condiciones de alerta de ingesta' : 'Sin condiciones de alerta de ingesta'); banner.append(heading);
  if (ingestion.conditions.length) {
    const conditions = document.createElement('ul');
    const kinds = {missing: 'Falta el intento diario esperado', failed: 'La última ejecución terminada falló', stalled: 'Una ejecución lleva al menos dos horas'};
    for (const condition of ingestion.conditions) conditions.append(node('li', (kinds[condition.kind] ?? 'Condición no reconocida') + (condition.run_id == null ? '' : ' · ejecución ' + condition.run_id)));
    banner.append(conditions);
  }
  if (ingestion.conditions_truncated) banner.append(node('p', 'Se muestran ' + ingestion.conditions.length + ' de ' + ingestion.condition_count + ' condiciones.'));
  const read = node('p', 'Lectura del ' + moment(ingestion.observed_at) + ' (hora Argentina).'); read.className = 'hint';
  results.append(banner, read);
  const runs = document.createElement('div'); runs.className = 'run-grid';
  runs.append(run('Último intento', ingestion.latest_attempt), run('Última ingesta exitosa', ingestion.latest_successful));
  results.append(runs);
  const average = queries.completed ? Number(queries.duration_ms_total) / queries.completed : null;
  const queryPanel = card('Consultas HTTP · proceso actual', tiles([
    ['Terminadas', count(queries.completed)], ['Duración promedio', average == null ? 'Sin datos' : milliseconds(average)],
    ['Con recomendación', count(queries.outcome.recommended ?? 0)], ['Sin alternativas', count(queries.outcome.no_feasible_stations ?? 0)],
    ['Sin cobertura', count(queries.outcome.insufficient_coverage ?? 0)], ['Con error HTTP', count(queries.outcome.http_error ?? 0)]
  ]));
  if (queries.status === 'degraded') { const warning = node('p', 'La última consulta tuvo un fallo operativo. Revisá la disponibilidad y los contadores del proveedor de rutas.'); warning.className = 'notice warning'; queryPanel.append(warning); }
  results.append(queryPanel);
  results.append(card('Rutas · caché del proceso', tiles([
    ['Reutilizaciones', count(routes.hits)], ['Faltantes en caché', count(routes.misses)], ['Solicitudes al proveedor', count(routes.requests)],
    ['Errores del proveedor', count(routes.errors)], ['Bloqueos por cupo', count(routes.limited)], ['Proveedor ocupado', count(routes.busy)], ['Entradas', count(routes.entries)]
  ])));
  const diagnostics = metrics.price_diagnostics;
  if (diagnostics) {
    const outcomes = diagnostics.outcome, average = diagnostics.completed ? Number(diagnostics.duration_ms_total) / diagnostics.completed : null;
    const labels = {not_observed: 'Sin consultas observadas', observed: 'Última lectura sin fallo operativo', degraded: 'Última lectura con fallo operativo'};
    const panel = card('Diagnóstico de precios · proceso actual', tiles([
      ['Estado', labels[diagnostics.status] ?? 'Estado desconocido'], ['Consultas', count(diagnostics.completed)],
      ['Con referencia', count(outcomes.reference_only ?? 0)], ['Sin contexto', count(outcomes.unavailable ?? 0)],
      ['Sin publicación', count(outcomes.not_found ?? 0)], ['Fallo de dependencia', count(outcomes.dependency_unavailable ?? 0)],
      ['Fallos internos', count(outcomes.internal_error ?? 0)], ['Duración promedio', average == null ? 'Sin datos' : milliseconds(average)],
      ['Última consulta', moment(diagnostics.last_completed_at_utc)]
    ]));
    if (diagnostics.status === 'degraded') { const warning = node('p', 'El último diagnóstico falló; revisá su configuración y datos. La recomendación habitual puede seguir disponible.'); warning.className = 'notice warning'; panel.append(warning); }
    const reference = diagnostics.last_reference;
    if (reference) {
      const methods = {bandera_reciente: 'Mediana reciente de la bandera', ultimo_precio: 'Último precio propio', mediana_previa: 'Mediana comparable previa'};
      panel.append(details([['Última referencia observada', methods[reference.method] ?? 'Método desconocido'], ['Versión', reference.version], ['Observada', moment(reference.observed_at_utc)]]));
    }
    panel.append(node('p', 'Son solicitudes observadas en este proceso; no miden precisión, deriva ni validez de alertas estadísticas. La última referencia puede ser anterior al último fallo.'));
    results.append(panel);
  }
  const notice = node('p', 'Los contadores no incluyen la CLI y las rutas grabadas no usan esta caché.'); notice.className = 'hint'; results.append(notice);
  const limit = node('p', 'Esta lectura recalcula condiciones; no crea ni resuelve alertas del monitor. Sin alertas no significa que los precios sean actuales. Histórico usa las mismas reglas, aunque no tenga una tarea diaria programada.');
  limit.className = 'hint'; results.append(limit);
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
