// QA aislada: precios del escenario histórico y rutas sintéticas del servidor fixture.
const {test, before, after} = require('node:test');
const assert = require('node:assert/strict');
const {spawn} = require('node:child_process');
const fs = require('node:fs');
const path = require('node:path');
const {chromium} = require('playwright');
const axe = require('axe-core');
const root = path.resolve(__dirname, '../..');
let server, browser, base;
const artifacts = process.env.WEB_TEST_ARTIFACTS || '/tmp/nafta2go-web-artifacts';
before(async () => {
  server = spawn(process.env.WEB_TEST_PYTHON || 'python', ['tests/browser/server.py'], {cwd: root, env: {...process.env, PYTHONPATH: root}, stdio: ['ignore', 'pipe', 'pipe']});
  base = await new Promise((resolve, reject) => {
    let log = '';
    const timer = setTimeout(() => reject(new Error('El servidor de QA no inició: ' + log)), 30000);
    server.once('exit', () => { clearTimeout(timer); reject(new Error('Servidor terminado: ' + log)); });
    for (const stream of [server.stdout, server.stderr]) stream.on('data', data => {
      log += data.toString(); const match = log.match(/http:\/\/127\.0\.0\.1:\d+/);
      if (match) { clearTimeout(timer); resolve(match[0]); }
    });
  });
  browser = await chromium.launch({headless: true});
  fs.mkdirSync(artifacts, {recursive: true});
  fs.writeFileSync(path.join(artifacts, 'entorno.json'), JSON.stringify({observed_at: new Date().toISOString(), browser: browser.version(), playwright: require('playwright/package.json').version, axe: axe.version, node: process.versions.node, routes: 'synthetic-web-test-fixture', prices: 'historical-repository-scenario'}, null, 2));
});
after(async () => { if (browser) await browser.close(); if (server) server.kill('SIGTERM'); });
async function pageFor(options = {}) {
  const context = await browser.newContext({locale: 'es-AR', viewport: {width: 1440, height: 1000}, ...options});
  await context.route('**/*', route => route.request().url().startsWith(base + '/') ? route.continue() : route.abort());
  const page = await context.newPage(); await page.goto(base); return page;
}
async function ready(page, destination = false, code = 'codigo-web-de-prueba') {
  for (const key of ['origin','destination']) await page.locator('#' + key + '-coordinates').evaluate(el => el.open = true);
  await page.locator('[name=origin_lat]').fill('-34.6037'); await page.locator('[name=origin_lon]').fill('-58.3816');
  if (destination) {
    await page.locator('[name=destination_lat]').fill('-34.5627'); await page.locator('[name=destination_lon]').fill('-58.4565');
  } else await page.locator('#return').check();
  await page.locator('#access').fill(code);
}
async function send(page) { await page.locator('#submit').click(); await page.waitForFunction(() => !document.querySelector('#submit').disabled); }
async function accessible(page) {
  await page.evaluate(axe.source);
  const result = await page.evaluate(() => axe.run(document, {runOnly: {type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa']}}));
  fs.writeFileSync(path.join(artifacts, 'axe-' + (++accessible.count) + '.json'), JSON.stringify({version: result.testEngine.version, violations: result.violations, incomplete: result.incomplete}, null, 2));
  assert.deepEqual(result.violations.map(v => ({id: v.id, impact: v.impact, nodes: v.nodes.map(n => n.target)})), []);
}
accessible.count = 0;
test('los descartes explican la falta de dirección sin mostrar null', async () => {
  const page = await pageFor();
  try {
    await ready(page); await page.locator('[name=remaining_l]').fill('0');
    await page.route('**/api/v1/recommendations', async route => {
      const response = await route.fetch(), payload = await response.json();
      for (const row of payload.evaluations) row.address = null;
      await route.fulfill({json: payload});
    });
    await send(page);
    const discarded = page.locator('details li');
    assert.ok(await discarded.count() > 0);
    assert.match(await discarded.first().textContent(), /Dirección no informada/);
    assert.doesNotMatch(await page.locator('#results').textContent(), /\bnull\b/);
  } finally { await page.context().close(); }
});
async function reach(page, selector) {
  for (let i = 0; i < 90; i++) {
    if (await page.locator(selector).first().evaluate(el => el === document.activeElement)) return;
    await page.keyboard.press('Tab');
  }
  throw new Error('No se alcanzó con teclado: ' + selector);
}
async function enter(page, selector, value) { await reach(page, selector); await page.keyboard.press('ControlOrMeta+A'); await page.keyboard.type(value); }
test('formulario, respuesta del backend con fixtures y accesibilidad en escritorio', async () => {
  const page = await pageFor();
  try {
    const ors = page.locator('footer a[href="https://openrouteservice.org/"]');
    const osm = page.locator('footer a[href="https://www.openstreetmap.org/copyright"]');
    assert.equal(await ors.isVisible(), true); assert.equal(await osm.isVisible(), true);
    assert.equal(await ors.getAttribute('rel'), 'noopener noreferrer');
    assert.equal(await osm.getAttribute('rel'), 'noopener noreferrer');
    await accessible(page); await ready(page, true);
    const request = page.waitForRequest(r => r.url().endsWith('/api/v1/recommendations'));
    await send(page); const sent = (await request).postDataJSON();
    assert.deepEqual(sent.destination, {lat: -34.5627, lon: -58.4565}); assert.equal(typeof sent.budget_ars, 'string');
    assert.match(await page.locator('#status').innerText(), /Encontramos/);
    assert.match(await page.locator('#results').innerText(), /ESCENARIO HISTÓRICO/);
    assert.match(await page.locator('#results').innerText(), /Vigencia máxima aplicada: 29 días/);
    assert.ok(await page.locator('article').count() > 0);
    assert.equal(await page.locator('a.navigate').count(), await page.locator('article').count());
    const first = page.locator('article').first();
    assert.match(await first.innerText(), /Costo de la carga/); assert.doesNotMatch(await first.innerText(), /Autonomía final/);
    await first.locator('.card-detail summary').click();
    assert.match(await first.innerText(), /Autonomía final/);
    const shown = await first.locator('dd').allInnerTexts();
    assert.ok(shown.every(text => !/,\d{3}\b/.test(text)), shown.join(' | '));
    assert.match(await first.locator('.key-figures').innerText(), /~\d+ min/);
    const link = page.locator('a.navigate').first();
    assert.equal(await link.getAttribute('rel'), 'noopener noreferrer'); assert.equal(await link.getAttribute('target'), '_blank');
    const url = new URL(await link.getAttribute('href'));
    assert.equal(url.origin, 'https://www.google.com'); assert.ok(!url.searchParams.has('origin'));
    assert.equal(await page.evaluate(() => localStorage.length + sessionStorage.length), 0);
    assert.equal(new URL(page.url()).search, ''); await accessible(page);
    await page.screenshot({path: path.join(artifacts, 'escritorio.png'), fullPage: true});
  } finally { await page.context().close(); }
});
for (const destination of [false, true]) test('recorrido completo por teclado ' + (destination ? 'UC01' : 'UC02'), async () => {
  const page = await pageFor();
  try {
    await page.keyboard.press('Tab'); assert.equal(await page.locator('.skip').evaluate(el => el === document.activeElement), true);
    await page.keyboard.press('Enter');
    await reach(page, '#origin-coordinates summary'); await page.keyboard.press('Enter');
    await reach(page, '#destination-coordinates summary'); await page.keyboard.press('Enter');
    await enter(page, '[name=origin_lat]', '-34.6037'); await enter(page, '[name=origin_lon]', '-58.3816');
    if (destination) {
      await enter(page, '[name=destination_lat]', '-34.5627'); await enter(page, '[name=destination_lon]', '-58.4565');
    } else { await reach(page, '#return'); await page.keyboard.press('Space'); }
    await enter(page, '#access', 'codigo-web-de-prueba'); await reach(page, '#submit'); await page.keyboard.press('Enter');
    await page.waitForFunction(() => document.querySelector('#status').textContent.startsWith('Encontramos'));
    assert.equal(await page.evaluate(() => document.activeElement.id), 'results');
    await reach(page, 'a.navigate'); assert.equal(await page.locator('a.navigate').first().evaluate(el => getComputedStyle(el).outlineWidth), '3px');
  } finally { await page.context().close(); }
});
test('volver a donde estoy copia el origen en el destino y lo bloquea', async () => {
  const page = await pageFor();
  try {
    for (const key of ['origin','destination']) await page.locator('#' + key + '-coordinates').evaluate(el => el.open = true);
    const lat = page.locator('[name=destination_lat]'), lon = page.locator('[name=destination_lon]');
    assert.equal(await lat.isVisible(), true); assert.equal(await page.locator('#return').isChecked(), false);
    await page.locator('[name=origin_lat]').fill('-34.6037'); await page.locator('[name=origin_lon]').fill('-58.3816');
    await page.locator('#return').check();
    assert.deepEqual([await lat.inputValue(), await lon.inputValue()], ['-34.6037', '-58.3816']);
    assert.equal(await lat.evaluate(el => el.readOnly), true);
    await page.locator('[name=origin_lat]').fill('-34.6100'); assert.equal(await lat.inputValue(), '-34.6100');
    await page.locator('#access').fill('codigo-web-de-prueba');
    const request = page.waitForRequest(r => r.url().endsWith('/api/v1/recommendations'));
    await send(page); assert.equal((await request).postDataJSON().destination, null);
    await page.locator('#return').uncheck();
    assert.deepEqual([await lat.inputValue(), await lat.evaluate(el => el.readOnly)], ['', false]);
    await accessible(page);
  } finally { await page.context().close(); }
});
test('UC06 por teclado: descartes sin ganadoras inventadas', async () => {
  const page = await pageFor();
  try {
    await ready(page); await page.locator('[name=remaining_l]').focus();
    await page.keyboard.press('ControlOrMeta+A'); await page.keyboard.type('0');
    await reach(page, '#submit'); await page.keyboard.press('Enter');
    await page.waitForFunction(() => document.querySelector('#status').textContent.includes('sin alternativas'));
    assert.equal(await page.locator('article').count(), 0); await reach(page, '#results > details > summary'); await page.keyboard.press('Enter');
    assert.equal(await page.locator('#results > details').evaluate(el => el.open), true);
    assert.match(await page.locator('#results > details').innerText(), /combustible para llegar/); await accessible(page);
  } finally { await page.context().close(); }
});
test('validación física, corrección y código inválido sin guardar credenciales', async () => {
  const page = await pageFor();
  try {
    await ready(page, false, 'incorrecto'); await page.locator('[name=remaining_l]').fill('60');
    await page.locator('#submit').click(); assert.equal(await page.evaluate(() => document.activeElement.name), 'remaining_l');
    await page.locator('[name=tank_capacity_l]').fill('70'); await send(page);
    assert.match(await page.locator('#error').innerText(), /código de acceso no es válido/);
    assert.equal(await page.evaluate(() => document.activeElement.id), 'error');
    assert.equal(await page.locator('article').count(), 0); await accessible(page);
    await page.reload(); assert.equal(await page.locator('#access').inputValue(), '');
  } finally { await page.context().close(); }
});
test('móvil emulado, geolocalización simulada y búsqueda sin destino', async () => {
  const page = await pageFor({viewport: {width: 390, height: 844}, isMobile: true, hasTouch: true, permissions: ['geolocation'], geolocation: {latitude: -34.6037, longitude: -58.3816}});
  try {
    await page.locator('#locate').click(); await page.waitForFunction(() => document.querySelector('[name=origin_lat]').value !== '');
    await page.locator('#return').check(); assert.equal(await page.locator('[name=destination_lat]').inputValue(), '-34.6037');
    await page.locator('#access').fill('codigo-web-de-prueba'); const request = page.waitForRequest(r => r.url().endsWith('/api/v1/recommendations'));
    await send(page); assert.equal((await request).postDataJSON().destination, null);
    assert.match(await page.locator('#status').innerText(), /Encontramos/);
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)); await accessible(page);
    await page.screenshot({path: path.join(artifacts, 'movil-emulado.png'), fullPage: true});
  } finally { await page.context().close(); }
});
test('sin cobertura: mensaje explícito, sin enlaces ni tarjetas', async () => {
  const page = await pageFor();
  try {
    await ready(page); await page.locator('[name=origin_lat]').fill('-34.71'); await page.locator('[name=origin_lon]').fill('-58.33'); await send(page);
    assert.match(await page.locator('#results').innerText(), /No hay cobertura suficiente/);
    assert.equal(await page.locator('article, a.navigate').count(), 0); await accessible(page);
  } finally { await page.context().close(); }
});
test('cuota y carga no muestran resultados viejos', async () => {
  const page = await pageFor();
  try {
    await ready(page); await send(page); assert.ok(await page.locator('article').count());
    await page.route('**/api/v1/recommendations', async route => {
      await new Promise(resolve => setTimeout(resolve, 250));
      await route.fulfill({status: 503, json: {detail: {code: 'routes_quota_exceeded'}}});
    });
    await page.locator('#submit').click(); assert.equal(await page.locator('#submit').isDisabled(), true);
    assert.equal(await page.locator('article').count(), 0);
    await page.waitForFunction(() => !document.querySelector('#submit').disabled);
    assert.match(await page.locator('#error').innerText(), /límite del servicio/); await accessible(page);
  } finally { await page.context().close(); }
});
test('texto remoto y enlaces maliciosos no se convierten en HTML o javascript', async () => {
  const page = await pageFor();
  try {
    await ready(page);
    await page.route('**/api/v1/recommendations', async route => {
      const response = await route.fetch(), payload = await response.json();
      for (const row of payload.evaluations) row.brand = '<img src=x onerror="window.XSS=true">';
      for (const link of payload.navigation) link.url = 'javascript:window.XSS=true';
      await route.fulfill({json: payload});
    });
    await send(page); assert.ok(await page.locator('article').count());
    assert.equal(await page.locator('img, script:not([src]), a.navigate').count(), 0);
    assert.equal(await page.evaluate(() => window.XSS), undefined);
    assert.match(await page.locator('article h3').first().innerText(), /<img/);
  } finally { await page.context().close(); }
});
test('ubicación denegada conserva el ingreso manual y el diseño a 320 px', async () => {
  const page = await pageFor({viewport: {width: 320, height: 740}});
  try {
    await page.evaluate(() => { navigator.geolocation.getCurrentPosition = (_ok, reject) => reject({code: 1}); });
    await page.locator('#locate').click();
    assert.match(await page.locator('#location-status').innerText(), /no dieron permiso.*manualmente/);
    assert.equal(await page.locator('#submit').isDisabled(), false);
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
    await ready(page); await send(page); assert.match(await page.locator('#status').innerText(), /Encontramos/);
  } finally { await page.context().close(); }
});
test('timeout del proveedor y fallo de red ofrecen mensajes recuperables', async () => {
  const page = await pageFor();
  try {
    await ready(page);
    await page.route('**/api/v1/recommendations', route => route.fulfill({status: 504, json: {detail: {code: 'routes_timeout'}}}));
    await send(page); assert.match(await page.locator('#error').innerText(), /rutas demoró demasiado/);
    await page.unroute('**/api/v1/recommendations');
    await page.route('**/api/v1/recommendations', route => route.abort('failed'));
    await send(page); assert.match(await page.locator('#error').innerText(), /Revisá tu conexión/);
    assert.equal(await page.locator('article').count(), 0);
  } finally { await page.context().close(); }
});

async function operation(page, code = 'codigo-operacion-de-prueba') {
  await page.goto(base + '/operacion'); await page.locator('#operation-access').fill(code);
}
async function readOperation(page) {
  await page.locator('#operation-submit').click();
  await page.waitForFunction(() => !document.querySelector('#operation-submit').disabled);
}
test('panel: acceso por teclado y lectura real de la API sin persistir código', async () => {
  const page = await pageFor();
  try {
    await page.goto(base + '/operacion'); await accessible(page);
    assert.equal(await page.locator('#operation-results').innerText(), '');
    await page.keyboard.press('Tab'); await page.keyboard.press('Enter');
    await enter(page, '#operation-access', 'codigo-operacion-de-prueba');
    await page.locator('#operation-source').selectOption('historico');
    const request = page.waitForRequest(r => r.url().includes('/operations/ingestion?'));
    await reach(page, '#operation-submit'); await page.keyboard.press('Enter');
    await page.waitForFunction(() => document.querySelector('#operation-status').textContent.startsWith('Estado actualizado'));
    const sent = await request;
    assert.equal(new URL(sent.url()).searchParams.get('source'), 'historico');
    assert.equal(sent.headers().authorization, 'Bearer codigo-operacion-de-prueba');
    assert.equal(await page.evaluate(() => document.activeElement.id), 'operation-results');
    assert.match(await page.locator('#operation-results').innerText(), /Falta el intento diario esperado/);
    assert.match(await page.locator('#operation-results').innerText(), /No hay una ejecución registrada/);
    assert.equal(await page.evaluate(() => localStorage.length + sessionStorage.length), 0);
    assert.equal((await page.context().cookies()).length, 0);
    assert.equal(new URL(page.url()).search, ''); await accessible(page);
    await page.screenshot({path: path.join(artifacts, 'operacion-escritorio.png'), fullPage: true});
    await page.locator('#operation-clear').click();
    assert.equal(await page.locator('#operation-results').innerText(), '');
    assert.equal(await page.locator('#operation-access').inputValue(), '');
    assert.equal(await page.evaluate(() => document.activeElement.id), 'operation-access');
  } finally { await page.context().close(); }
});
test('panel: código inválido, dependencia caída y fallo de red retiran la lectura anterior', async () => {
  const page = await pageFor();
  try {
    await operation(page, 'incorrecto'); await readOperation(page);
    assert.match(await page.locator('#operation-error').innerText(), /código de acceso no es válido/);
    assert.equal(await page.evaluate(() => document.activeElement.id), 'operation-error'); await accessible(page);
    await page.locator('#operation-access').fill('codigo-operacion-de-prueba'); await readOperation(page);
    assert.ok(await page.locator('#operation-results article').count());
    await page.route('**/api/v1/operations/ingestion?*', route => route.fulfill({status: 503, json: {detail: {code: 'data_unavailable'}}}));
    await readOperation(page);
    assert.equal(await page.locator('#operation-results').innerText(), '');
    assert.match(await page.locator('#operation-error').innerText(), /disponibilidad del servicio/);
    await page.unroute('**/api/v1/operations/ingestion?*');
    await page.route('**/api/v1/operations/ingestion?*', route => route.abort('failed'));
    await readOperation(page); assert.match(await page.locator('#operation-error').innerText(), /Revisá la conexión/);
  } finally { await page.context().close(); }
});
test('panel: limpiar durante carga cancela y no repone datos ni credenciales', async () => {
  const page = await pageFor();
  try {
    await operation(page); let release;
    const delayed = new Promise(resolve => { release = resolve; });
    await page.route('**/api/v1/operations', async route => {
      await delayed;
      await route.fulfill({json: {queries: {completed: 999, outcome: {}}, routes: {}}}).catch(() => {});
    });
    const request = page.waitForRequest(r => r.url().endsWith('/api/v1/operations'));
    await page.locator('#operation-submit').click(); await request;
    assert.equal(await page.locator('#operation-submit').isDisabled(), true);
    await page.locator('#operation-clear').click(); release();
    await page.waitForLoadState('networkidle');
    assert.equal(await page.locator('#operation-results').innerText(), '');
    assert.equal(await page.locator('#operation-access').inputValue(), '');
    assert.match(await page.locator('#operation-status').innerText(), /limpiados/);
    await page.reload(); assert.equal(await page.locator('#operation-access').inputValue(), '');
  } finally { await page.context().close(); }
});
test('panel móvil: fallo posterior al éxito, condiciones truncadas y texto remoto seguro', async () => {
  const page = await pageFor({viewport: {width: 390, height: 844}, isMobile: true, hasTouch: true});
  try {
    await operation(page);
    const run = {id: 8, status: 'succeeded', started_at: '2026-10-26T10:00:00+00:00', finished_at: '2026-10-26T10:01:00+00:00', duration_seconds: 60, price_rows: 12, stations: 8, rejected_rows: 1, rules_version: '<img src=x onerror="window.XSS=true">', sha256: 'a'.repeat(64), size_bytes: 1234};
    await page.route('**/api/v1/operations/ingestion?*', route => route.fulfill({json: {
      observed_at: run.finished_at, status: 'alerting', latest_attempt: {...run, id: 9, status: 'failed'}, latest_successful: run,
      conditions: [{kind: 'failed', run_id: 9}], condition_count: 21, conditions_truncated: true
    }}));
    await readOperation(page);
    assert.match(await page.locator('#operation-results').innerText(), /Fallida/);
    assert.match(await page.locator('#operation-results').innerText(), /Exitosa/);
    assert.match(await page.locator('#operation-results').innerText(), /Se muestran 1 de 21/);
    assert.equal(await page.locator('img, script:not([src])').count(), 0);
    assert.equal(await page.evaluate(() => window.XSS), undefined);
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
    await accessible(page); await page.screenshot({path: path.join(artifacts, 'operacion-movil-emulado.png'), fullPage: true});
    await page.setViewportSize({width: 320, height: 740});
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
    await page.unroute('**/api/v1/operations/ingestion?*');
    await page.route('**/api/v1/operations/ingestion?*', route => route.fulfill({json: {
      observed_at: run.finished_at, status: 'healthy', conditions: [], latest_attempt: run, latest_successful: run
    }}));
    await readOperation(page); assert.match(await page.locator('#operation-results').innerText(), /Sin condiciones de alerta/);
    await page.locator('.brand').click(); await page.goBack();
    assert.equal(await page.locator('#operation-access').inputValue(), '');
    assert.equal(await page.locator('#operation-results').innerText(), '');
  } finally { await page.context().close(); }
});
test('panel: timeout cancela la lectura completa sin conservar datos', async () => {
  const page = await pageFor(); let release;
  try {
    await operation(page); await page.clock.install();
    const delayed = new Promise(resolve => { release = resolve; });
    await page.route('**/api/v1/operations', async route => {
      await delayed; await route.fulfill({json: {}}).catch(() => {});
    });
    const request = page.waitForRequest(r => r.url().endsWith('/api/v1/operations'));
    await page.locator('#operation-submit').click(); await request;
    await page.clock.runFor(15001);
    await page.waitForFunction(() => !document.querySelector('#operation-submit').disabled);
    assert.match(await page.locator('#operation-error').innerText(), /demoró demasiado/);
    assert.equal(await page.locator('#operation-results').innerText(), '');
    release(); await accessible(page);
  } finally { release?.(); await page.context().close(); }
});
test('panel: código pegado con espacios conserva acceso y header normalizado', async () => {
  const page = await pageFor();
  try {
    await operation(page, '  codigo-operacion-de-prueba  ');
    const request = page.waitForRequest(r => r.url().endsWith('/api/v1/operations'));
    await readOperation(page);
    assert.equal((await request).headers().authorization, 'Bearer codigo-operacion-de-prueba');
    assert.match(await page.locator('#operation-status').innerText(), /Estado actualizado/);
  } finally { await page.context().close(); }
});

 test('panel: el código del conductor se rechaza y el administrativo permite consultar', async () => {
  const page = await pageFor();
  try {
    await operation(page, 'codigo-web-de-prueba'); await readOperation(page);
    assert.match(await page.locator('#operation-error').innerText(), /código de acceso no es válido/);
    assert.equal(await page.locator('#operation-results').innerText(), '');
    await page.locator('#operation-access').fill('codigo-operacion-de-prueba'); await readOperation(page);
    assert.ok(await page.locator('#operation-results article').count());
  } finally { await page.context().close(); }
});

// Respuestas de referencia sintéticas: verifican presentación, no calidad estadística.
async function referenceScenario(page) {
  let data;
  await ready(page);
  await page.route('**/api/v1/recommendations', async route => {
    const response = await route.fetch();
    data = {...await response.json(), status: 'ready', data_run_id: 42};
    await route.fulfill({response, json: data});
  });
  await send(page);
  const row = data.evaluations.find(r => r.station_id === data.alternatives[0].station_id);
  const answer = {scope: 'published_price_retrospective', status: 'reference_only',
    station_id: Number(row.station_id), product_id: 2, schedule_id: 2, data_run_id: 42,
    official_price_ars_per_l: row.price_ars_per_l,
    published_at: new Date(row.published_at_local + '-03:00').toISOString(),
    reference_ars_per_l: '1000.000', difference_ars_per_l: '25.000',
    alert_level: 'not_calibrated', method: 'bandera_reciente', version: 'e'.repeat(64)};
  const card = page.locator('article').first(); await card.locator('.card-detail > summary').click();
  return {data, row, answer, card};
}
async function readReference(page, card) {
  const detail = card.locator('.card-detail');
  if (!await detail.evaluate(el => el.open)) await detail.locator(':scope > summary').click();
  await card.locator('.price-reference-button').click();
  await page.waitForFunction(() => !document.querySelector('.price-reference-button').disabled);
  return card.locator('.price-reference-result').innerText();
}
test('referencia: sólo bajo pedido, con consulta congelada, privacidad y texto seguro', async () => {
  const page = await pageFor(); const requests = [];
  try {
    page.on('request', r => { if (r.url().includes('/price-diagnostics/')) requests.push(r); });
    const {answer, card} = await referenceScenario(page);
    assert.equal(requests.length, 0);
    await page.locator('[name=fuel_type]').selectOption('premium');
    await page.locator('[name=schedule_id]').selectOption('3');
    await page.locator('#access').fill('  codigo-web-de-prueba  ');
    await page.context().addCookies([{name: 'private-cookie', value: 'qa', url: base}]);
    answer.version = '<img src=x onerror="window.referenceAttack=1">';
    await page.route('**/api/v1/price-diagnostics/**', route => route.fulfill({json: answer}));
    const text = await readReference(page, card);
    assert.match(text, /Referencia histórica de esta publicación/);
    assert.match(text, /No estima el precio actual/); assert.match(text, /no hay una alerta validada/);
    const url = new URL(requests[0].url());
    assert.equal(url.search, '?product_id=2&schedule_id=2');
    assert.equal(requests[0].headers().authorization, 'Bearer codigo-web-de-prueba');
    assert.equal(requests[0].headers().cookie, undefined);
    assert.equal(new URL(page.url()).search, '');
    await card.locator('.price-reference-result summary').click();
    assert.match(await card.locator('.price-reference-result').innerText(), /<img/);
    assert.equal(await card.locator('.price-reference-result img').count(), 0);
    assert.equal(await page.evaluate(() => window.referenceAttack), undefined);
    assert.equal(await page.evaluate(() => localStorage.length + sessionStorage.length), 0);
    await accessible(page);
    answer.version = 'e'.repeat(64); await readReference(page, card);
    await card.locator('.price-reference-result summary').click();
    await page.setViewportSize({width: 320, height: 800});
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
    await accessible(page);
  } finally { await page.context().close(); }
});
test('referencia: errores, cambios de publicación y abstención retiran datos anteriores', async () => {
  const page = await pageFor();
  try {
    const {answer, card} = await referenceScenario(page); let reply = {json: answer};
    await page.route('**/api/v1/price-diagnostics/**', route => reply === 'network' ? route.abort('failed') : route.fulfill(reply));
    assert.match(await readReference(page, card), /Referencia histórica/);
    for (const [value, expected] of [
      [{status: 401, json: {detail: 'secreto'}}, /código de acceso/],
      [{status: 404, json: {detail: 'secreto'}}, /Volvé a buscar/],
      [{status: 503, json: {detail: 'secreto'}}, /no está disponible/],
      [{json: {...answer, data_run_id: 99}}, /no coincide/],
      [{json: {...answer, official_price_ars_per_l: '1'}}, /no coincide/],
      [{json: {...answer, published_at: '2020-01-01T00:00:00Z'}}, /no coincide/],
      [{json: {...answer, status: 'unavailable', reference_ars_per_l: null}}, /historia comparable/],
      [{json: {...answer, alert_level: 'normal'}}, /referencia válida/],
      [{status: 200, contentType: 'text/html', body: 'secreto'}, /Revisá la conexión/],
      ['network', /Revisá la conexión/],
    ]) {
      reply = value; const text = await readReference(page, card);
      assert.match(text, expected); assert.doesNotMatch(text, /secreto|Referencia histórica de esta publicación/);
    }
  } finally { await page.context().close(); }
});
test('referencia: cancelar al buscar o salir evita respuestas tardías y permite reintentar', async () => {
  const page = await pageFor(); let release;
  try {
    const {answer, card} = await referenceScenario(page);
    const delayed = new Promise(resolve => { release = resolve; });
    await page.route('**/api/v1/price-diagnostics/**', async route => { await delayed; await route.fulfill({json: answer}).catch(() => {}); });
    const requested = page.waitForRequest(r => r.url().includes('/price-diagnostics/'));
    await card.locator('.price-reference-button').click(); await requested;
    await send(page); release();
    assert.equal(await page.locator('.price-reference-result').first().innerText(), '');
    await page.unroute('**/api/v1/price-diagnostics/**');
    await page.route('**/api/v1/price-diagnostics/**', route => route.fulfill({json: answer}));
    await readReference(page, page.locator('article').first());
    await page.evaluate(() => window.dispatchEvent(new Event('pagehide')));
    assert.equal(await page.locator('#access').inputValue(), '');
    assert.equal(await page.locator('.price-reference-result').first().innerText(), '');
    await page.locator('#access').fill('codigo-web-de-prueba');
    assert.match(await readReference(page, page.locator('article').first()), /Referencia histórica/);
  } finally { release?.(); await page.context().close(); }
});
test('referencia: espera acotada y ausencia en escenarios históricos', async () => {
  const page = await pageFor(); let release;
  try {
    await ready(page); await send(page);
    assert.equal(await page.locator('.price-reference-button').count(), 0);
    const {answer, card} = await referenceScenario(page);
    await page.clock.install(); const delayed = new Promise(resolve => { release = resolve; });
    await page.route('**/api/v1/price-diagnostics/**', async route => { await delayed; await route.fulfill({json: answer}).catch(() => {}); });
    await card.locator('.price-reference-button').click(); await page.clock.runFor(15001);
    await page.waitForFunction(() => !document.querySelector('.price-reference-button').disabled);
    assert.match(await card.locator('.price-reference-result').innerText(), /demoró demasiado/);
    release();
  } finally { release?.(); await page.context().close(); }
});
function staleBlock(items) {
  return {status: 'available', data_run_id: 1, method: 'bandera_reciente', version: 'stale-estimate-v1', evidence: 'evidencia/estimacion-antiguos-2026-11',
    min_age_days: 30, max_age_days: 120, notice: 'Estimación a partir de precios recientes de la misma bandera: no es un precio oficial.', items};
}
const staleItem = {station_id: '501', company: 'EMPRESA', brand: '<img src=x onerror="window.pwned=1">', address: 'CALLE 1', official_price_ars_per_l: '1500.000',
  official_published_at_local: '2026-09-10T08:00:00', official_age_days: 45.2, estimate_ars_per_l: '1700.000',
  reference_from_local: '2026-10-19T09:00:00', reference_to_local: '2026-10-26T09:00:00', reference_count: 3, method: 'bandera_reciente', version: 'stale-estimate-v1'};
test('las estimaciones de precios desactualizados se muestran aparte y rotuladas', async () => {
  for (const viewport of [{width: 1440, height: 1000}, {width: 320, height: 800}]) {
    const page = await pageFor({viewport});
    try {
      await ready(page);
      await page.route('**/api/v1/recommendations', async route => {
        const response = await route.fetch(), payload = await response.json();
        const navigation = {url: 'https://www.google.com/maps/dir/?api=1&destination=-34.6%2C-58.45&travelmode=driving&dir_action=navigate', label: 'Cómo llegar a la estación — CALLE 1'};
        payload.stale_price_estimates = staleBlock([{...staleItem, navigation}, {...staleItem, station_id: '502', estimate_ars_per_l: null}, {...staleItem, station_id: '503', official_published_at_local: 'ayer'},
          {...staleItem, station_id: '504', navigation: {url: 'javascript:window.pwned=1', label: 'x'}}]);
        await route.fulfill({json: payload});
      });
      await send(page);
      const section = page.getByRole('region', {name: 'Estaciones con precio desactualizado'});
      assert.equal(await section.isVisible(), true);
      assert.equal(await section.locator('article').count(), 2);
      const link = section.locator('a.navigate');
      assert.equal(await link.count(), 1);
      assert.equal(await link.getAttribute('rel'), 'noopener noreferrer'); assert.equal(await link.getAttribute('target'), '_blank');
      assert.equal(new URL(await link.getAttribute('href')).origin, 'https://www.google.com');
      const text = await section.textContent();
      assert.match(text, /ESTIMADO/);
      assert.match(text, /no es un precio oficial/);
      assert.match(text, /más de 30 días/);
      assert.match(text, /1\.500 ARS\/L · publicado el 10\/09\/2026 \(hace 45,2 días\)/);
      assert.match(text, /Precio estimado1\.700 ARS\/L/);
      assert.match(text, /Mediana de 3 precios de la misma bandera entre el 19\/10\/2026 y el 26\/10\/2026/);
      assert.equal(await section.locator('img').count(), 0);
      assert.equal(await page.evaluate(() => window.pwned), undefined);
      assert.equal(await page.locator('#results > article').filter({hasText: 'ESTIMADO'}).count(), 0);
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), true);
      await accessible(page);
    } finally { await page.context().close(); }
  }
});
test('sin estimaciones disponibles no aparece la sección', async () => {
  const page = await pageFor();
  try {
    await ready(page);
    await page.route('**/api/v1/recommendations', async route => {
      const response = await route.fetch(), payload = await response.json();
      payload.stale_price_estimates = {...staleBlock([staleItem]), status: 'no_current_data'};
      await route.fulfill({json: payload});
    });
    await send(page);
    assert.equal(await page.locator('.stale-estimates').count(), 0);
    assert.doesNotMatch(await page.locator('#results').textContent(), /ESTIMADO/);
  } finally { await page.context().close(); }
});

for (const withDestination of [false, true]) test('mapa del viaje con parada y Waze: ' + (withDestination ? 'UC01' : 'UC02'), async () => {
  const page = await pageFor();
  const external = [];
  page.on('request', request => { if (!request.url().startsWith(base + '/')) external.push(request.url()); });
  try {
    await ready(page, withDestination);
    const request = page.waitForRequest(r => r.url().endsWith('/api/v1/recommendations'));
    await send(page); const query = (await request).postDataJSON();
    const card = page.locator('article').first();
    await reach(page, '.navigation-choices > summary'); await page.keyboard.press('Enter');
    const station = new URL(await card.locator('a.navigate').getAttribute('href')).searchParams.get('destination');
    const routeLink = card.locator('a.trip-map'), url = new URL(await routeLink.getAttribute('href'));
    assert.equal(url.origin, 'https://www.google.com'); assert.equal(url.pathname, '/maps/dir/');
    assert.equal(url.searchParams.get('api'), '1'); assert.equal(url.searchParams.get('travelmode'), 'driving');
    assert.equal(url.searchParams.get('origin'), query.origin.lat + ',' + query.origin.lon);
    const end = query.destination || query.origin;
    assert.equal(url.searchParams.get('destination'), end.lat + ',' + end.lon);
    assert.equal(url.searchParams.get('waypoints'), station);
    assert.deepEqual([...url.searchParams.keys()].sort(), ['api','destination','origin','travelmode','waypoints']);
    assert.equal(await routeLink.getAttribute('rel'), 'noopener noreferrer');
    assert.equal(await routeLink.getAttribute('target'), '_blank');
    const waze = new URL(await card.locator('a.waze-map').getAttribute('href'));
    assert.equal(waze.origin, 'https://waze.com'); assert.equal(waze.pathname, '/ul');
    assert.equal(waze.searchParams.get('ll'), station); assert.equal(waze.searchParams.get('navigate'), 'yes');
    assert.equal(waze.searchParams.has('origin'), false);
    assert.match(await card.innerText(), /Google Maps recibe el origen/);
    assert.match(await card.innerText(), /destino final.*aparte/);
    const original = url.href;
    await page.locator('[name=origin_lat]').fill('-34.61');
    assert.equal(await routeLink.getAttribute('href'), original);
    assert.deepEqual(external, []);
    assert.equal(await page.evaluate(() => localStorage.length + sessionStorage.length), 0);
    await reach(page, 'a.trip-map'); assert.equal(await routeLink.evaluate(el => el === document.activeElement), true);
    await page.setViewportSize({width: 390, height: 844}); await accessible(page);
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
    await page.screenshot({path: path.join(artifacts, 'mapas-' + (withDestination ? 'uc01' : 'uc02') + '.png'), fullPage: true});
    await page.evaluate(() => window.dispatchEvent(new Event('pagehide')));
    assert.equal(await page.locator('a.trip-map').count(), 0);
  } finally { await page.context().close(); }
});

test('navegación inválida no crea enlaces externos ni expone el origen', async () => {
  const page = await pageFor();
  try {
    await ready(page);
    await page.route('**/api/v1/recommendations', async route => {
      const response = await route.fetch(), value = await response.json();
      for (const item of value.navigation) item.url = 'https://www.google.com/maps/dir/?destination=NaN%2C-58.4';
      await route.fulfill({json: value});
    });
    await send(page);
    assert.equal(await page.locator('.navigation-options').count(), 0);
  } finally { await page.context().close(); }
});

test('panel: diagnóstico observado, degradación y versión segura en móvil', async () => {
  const page = await pageFor();
  try {
    await operation(page); await readOperation(page);
    const panel = page.getByRole('heading', {name: 'Diagnóstico de precios · proceso actual'});
    assert.equal(await panel.isVisible(), true);
    assert.match(await panel.locator('..').innerText(), /Sin consultas observadas/);
    await page.route('**/api/v1/operations', async route => {
      const response = await route.fetch(), value = await response.json();
      value.queries.status = 'degraded';
      value.price_diagnostics = {scope: 'process', status: 'degraded', completed: 4,
        duration_ms_total: 120, outcome: {reference_only: 1, unavailable: 1, dependency_unavailable: 2},
        last_completed_at_utc: '2026-11-20T02:00:00+00:00',
        last_reference: {method: 'bandera_reciente', version: '<img src=x onerror="window.metricAttack=true">', observed_at_utc: '2026-11-19T18:00:00+00:00'}};
      await route.fulfill({json: value});
    });
    await page.locator('#operation-submit').click();
    await page.waitForFunction(() => !document.querySelector('#operation-submit').disabled);
    const text = await panel.locator('..').innerText();
    assert.match(text, /Última lectura con fallo operativo/);
    assert.match(text, /último diagnóstico falló/);
    assert.match(text, /no miden precisión/);
    assert.match(await page.locator('#operation-results').innerText(), /última consulta tuvo un fallo operativo/);
    assert.equal(await page.locator('img').count(), 0);
    assert.equal(await page.evaluate(() => window.metricAttack), undefined);
    await page.setViewportSize({width: 320, height: 740});
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
    await accessible(page);
  } finally { await page.context().close(); }
});

test('buscar origen y destino por nombre, confirmar y consultar sin guardar texto', async () => {
  const page = await pageFor();
  const seen = [];
  try {
    await page.locator('#access').fill('codigo-web-de-prueba');
    await page.route('**/api/v1/places', async route => {
      const request = route.request(); seen.push(request.postDataJSON());
      assert.equal(new URL(request.url()).search, '');
      assert.match(request.headers().authorization, /^Bearer codigo-web-de-prueba$/);
      await route.fulfill({json: {items: [{label: '<img src=x onerror="window.placeAttack=1"> Hospital de prueba', lat: -34.5627, lon: -58.4565}]}});
    });
    await page.locator('#origin-place').fill('Corrientes 1234');
    assert.equal(seen.length, 0);
    await page.locator('#origin-search').click();
    await page.locator('#origin-place-results button').click();
    await page.locator('#destination-place').fill('Hospital de prueba');
    await page.locator('#destination-place').press('Enter');
    await reach(page, '#destination-place-results button'); await page.keyboard.press('Enter');
    assert.equal(await page.locator('#origin-coordinates').evaluate(el => el.open), false);
    assert.equal(await page.evaluate(() => window.placeAttack), undefined);
    assert.equal(await page.locator('img').count(), 0);
    assert.equal(seen.length, 2);
    const request = page.waitForRequest(r => r.url().endsWith('/api/v1/recommendations'));
    await send(page); const body = (await request).postDataJSON();
    assert.deepEqual(body.destination, {lat: -34.5627, lon: -58.4565});
    assert.ok(!JSON.stringify(body).includes('Hospital'));
    assert.equal(await page.evaluate(() => localStorage.length + sessionStorage.length), 0);
    await page.setViewportSize({width: 390, height: 844}); await accessible(page);
    await page.screenshot({path: path.join(artifacts, 'busqueda-lugares-movil.png'), fullPage: true});
    await page.locator('#destination-place').fill('Otro lugar');
    assert.equal(await page.locator('[name=destination_lat]').inputValue(), '');
    await page.locator('#submit').click();
    assert.match(await page.locator('#destination-place-status').innerText(), /Elegí un resultado/);
  } finally { await page.context().close(); }
});

test('buscador: errores recuperables, sin resultados y cancelación al editar o salir', async () => {
  const page = await pageFor();
  try {
    await page.locator('#origin-place').fill('Dirección de prueba');
    await page.locator('#origin-search').click();
    assert.match(await page.locator('#origin-place-status').innerText(), /código de acceso/);
    await page.locator('#access').fill('codigo-web-de-prueba');
    for (const status of [401, 429, 503]) {
      await page.route('**/api/v1/places', route => route.fulfill({status, json: {detail: {code: 'error'}}}));
      await page.locator('#origin-search').click();
      await page.waitForFunction(() => !document.querySelector('#origin-search').disabled);
      assert.equal(await page.locator('#origin-place-results button').count(), 0);
      assert.doesNotMatch(await page.locator('#origin-place-status').innerText(), /Buscando/);
      await page.unroute('**/api/v1/places');
    }
    await page.route('**/api/v1/places', route => route.fulfill({json: {items: []}}));
    await page.locator('#origin-search').click();
    await page.waitForFunction(() => !document.querySelector('#origin-search').disabled);
    assert.match(await page.locator('#origin-place-status').innerText(), /No encontramos/);
    await page.unroute('**/api/v1/places');
    let release; const pending = new Promise(resolve => release = resolve);
    await page.route('**/api/v1/places', async route => { await pending; await route.fulfill({json: {items: [{label: 'Respuesta vieja', lat: -34.6, lon: -58.4}]}}).catch(() => {}); });
    const request = page.waitForRequest('**/api/v1/places');
    await page.locator('#origin-search').click(); await request;
    await page.locator('#origin-place').fill('Nueva dirección'); release();
    await page.waitForTimeout(100);
    assert.equal(await page.locator('#origin-place-results button').count(), 0);
    assert.equal(await page.locator('[name=origin_lat]').inputValue(), '');
    await page.evaluate(() => window.dispatchEvent(new Event('pagehide')));
    assert.equal(await page.locator('#origin-place').inputValue(), '');
  } finally { await page.context().close(); }
});

test('ubicación: reintento acotado ante timeout y precisión visible', async () => {
  const page = await pageFor();
  try {
    await page.evaluate(() => {
      window.geoOptions = [];
      navigator.geolocation.getCurrentPosition = (ok, fail, options) => {
        window.geoOptions.push(options);
        if (window.geoOptions.length === 1) fail({code: 3});
        else ok({coords: {latitude: -34.6037, longitude: -58.3816, accuracy: 75}});
      };
    });
    await page.locator('#locate').click();
    assert.match(await page.locator('#location-status').innerText(), /±75 m/);
    assert.equal(await page.locator('[name=origin_lat]').inputValue(), '-34.6037');
    const options = await page.evaluate(() => window.geoOptions);
    assert.equal(options.length, 2); assert.equal(options[0].maximumAge, 60000);
    assert.equal(options[1].enableHighAccuracy, true);
    await page.locator('#return').check();
    assert.equal(await page.locator('#destination-place').inputValue(), 'Mi ubicación');
    assert.equal(await page.locator('#destination-search').isDisabled(), true);
    await page.evaluate(() => { window.timeoutCalls = 0; navigator.geolocation.getCurrentPosition = (_ok, fail) => { window.timeoutCalls++; fail({code: 3}); }; });
    await page.locator('#locate').click();
    assert.equal(await page.evaluate(() => window.timeoutCalls), 2);
    assert.match(await page.locator('#location-status').innerText(), /no respondió.*Buscá tu dirección/);
    assert.equal(await page.locator('[name=origin_lat]').inputValue(), '');
    assert.equal(await page.locator('#locate').innerText(), 'Usar mi ubicación');
  } finally { await page.context().close(); }
});

test('ubicación: cancelar impide que una respuesta tardía reemplace el origen', async () => {
  const page = await pageFor();
  try {
    await page.evaluate(() => { navigator.geolocation.getCurrentPosition = ok => window.latePosition = ok; });
    await page.locator('#locate').click();
    assert.equal(await page.locator('#locate').innerText(), 'Cancelar ubicación');
    await page.locator('#locate').click();
    await page.evaluate(() => window.latePosition({coords: {latitude: -34.6037, longitude: -58.3816}}));
    assert.equal(await page.locator('[name=origin_lat]').inputValue(), '');
    assert.match(await page.locator('#location-status').innerText(), /cancelada.*dirección/);
    await page.locator('#locate').click();
    await page.locator('#origin-place').fill('Dirección elegida');
    await page.evaluate(() => window.latePosition({coords: {latitude: -34.6037, longitude: -58.3816}}));
    assert.equal(await page.locator('[name=origin_lat]').inputValue(), '');
    await accessible(page);
  } finally { await page.context().close(); }
});
