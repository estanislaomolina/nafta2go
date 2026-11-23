// Capturar el Grafana local de QA con cookies; nunca exportar credenciales.
const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require('playwright');

(async () => {
  const [base, passwordFile, output, project] = process.argv.slice(2);
  if (!['127.0.0.1', 'localhost'].includes(new URL(base).hostname)) {
    throw new Error('La captura de QA sólo admite loopback');
  }
  const browser = await chromium.launch({ headless: true });
  try {
    const context = await browser.newContext({ viewport: { width: 1600, height: 1900 } });
    const login = await context.request.post(base + '/login', {
      data: { user: 'admin', password: fs.readFileSync(passwordFile, 'utf8') },
    });
    if (!login.ok()) throw new Error('Falló el login de QA');
    const page = await context.newPage();
    for (const name of ['business', 'operations']) {
      await page.goto(base + '/d/nafta2go-' + name + '?var-project=' + encodeURIComponent(project), {
        waitUntil: 'networkidle',
      });
      await page.waitForTimeout(4000);
      await page.screenshot({ path: path.join(output, name + '.png'), fullPage: true });
    }
  } finally {
    await browser.close();
  }
})();
