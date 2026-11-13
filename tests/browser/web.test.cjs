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
  await page.locator('[name=origin_lat]').fill('-34.6037'); await page.locator('[name=origin_lon]').fill('-58.3816');
  if (destination) {
    await page.locator('#return').uncheck();
    await page.locator('[name=destination_lat]').fill('-34.5627'); await page.locator('[name=destination_lon]').fill('-58.4565');
  }
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
async function reach(page, selector) {
  for (let i = 0; i < 45; i++) {
    if (await page.locator(selector).first().evaluate(el => el === document.activeElement)) return;
    await page.keyboard.press('Tab');
  }
  throw new Error('No se alcanzó con teclado: ' + selector);
}
async function enter(page, selector, value) { await reach(page, selector); await page.keyboard.press('ControlOrMeta+A'); await page.keyboard.type(value); }
test('formulario, respuesta del backend con fixtures y accesibilidad en escritorio', async () => {
  const page = await pageFor();
  try {
    await accessible(page); await ready(page, true);
    const request = page.waitForRequest(r => r.url().endsWith('/api/v1/recommendations'));
    await send(page); const sent = (await request).postDataJSON();
    assert.deepEqual(sent.destination, {lat: -34.5627, lon: -58.4565}); assert.equal(typeof sent.budget_ars, 'string');
    assert.match(await page.locator('#status').innerText(), /Encontramos/);
    assert.match(await page.locator('#results').innerText(), /ESCENARIO HISTÓRICO/);
    assert.match(await page.locator('#results').innerText(), /Vigencia máxima aplicada: 29 días/);
    assert.ok(await page.locator('article').count() > 0);
    assert.equal(await page.locator('a.navigate').count(), await page.locator('article').count());
    assert.match(await page.locator('article').first().innerText(), /Autonomía final/);
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
    await enter(page, '[name=origin_lat]', '-34.6037'); await enter(page, '[name=origin_lon]', '-58.3816');
    if (destination) {
      await reach(page, '#return'); await page.keyboard.press('Space');
      await enter(page, '[name=destination_lat]', '-34.5627'); await enter(page, '[name=destination_lon]', '-58.4565');
    }
    await enter(page, '#access', 'codigo-web-de-prueba'); await reach(page, '#submit'); await page.keyboard.press('Enter');
    await page.waitForFunction(() => document.querySelector('#status').textContent.startsWith('Encontramos'));
    assert.equal(await page.evaluate(() => document.activeElement.id), 'results');
    await reach(page, 'a.navigate'); assert.equal(await page.locator('a.navigate').first().evaluate(el => getComputedStyle(el).outlineWidth), '3px');
  } finally { await page.context().close(); }
});
test('UC06 por teclado: descartes sin ganadoras inventadas', async () => {
  const page = await pageFor();
  try {
    await ready(page); await page.locator('[name=remaining_l]').focus();
    await page.keyboard.press('ControlOrMeta+A'); await page.keyboard.type('0');
    await reach(page, '#submit'); await page.keyboard.press('Enter');
    await page.waitForFunction(() => document.querySelector('#status').textContent.includes('sin alternativas'));
    assert.equal(await page.locator('article').count(), 0); await reach(page, 'summary'); await page.keyboard.press('Enter');
    assert.equal(await page.locator('details').evaluate(el => el.open), true);
    assert.match(await page.locator('details').innerText(), /combustible para llegar/); await accessible(page);
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
    assert.match(await page.locator('#location-status').innerText(), /manualmente/);
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

async function operation(page, code = 'codigo-web-de-prueba') {
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
    await enter(page, '#operation-access', 'codigo-web-de-prueba');
    await page.locator('#operation-source').selectOption('historico');
    const request = page.waitForRequest(r => r.url().includes('/operations/ingestion?'));
    await reach(page, '#operation-submit'); await page.keyboard.press('Enter');
    await page.waitForFunction(() => document.querySelector('#operation-status').textContent.startsWith('Estado actualizado'));
    const sent = await request;
    assert.equal(new URL(sent.url()).searchParams.get('source'), 'historico');
    assert.equal(sent.headers().authorization, 'Bearer codigo-web-de-prueba');
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
    await page.locator('#operation-access').fill('codigo-web-de-prueba'); await readOperation(page);
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
    await operation(page, '  codigo-web-de-prueba  ');
    const request = page.waitForRequest(r => r.url().endsWith('/api/v1/operations'));
    await readOperation(page);
    assert.equal((await request).headers().authorization, 'Bearer codigo-web-de-prueba');
    assert.match(await page.locator('#operation-status').innerText(), /Estado actualizado/);
  } finally { await page.context().close(); }
});
