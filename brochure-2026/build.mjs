import { chromium } from 'playwright-core';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';

const dir = path.dirname(fileURLToPath(import.meta.url));
const output = path.join(dir, 'Epixeirimatiki-Asfalisi-2026.pdf');

const browser = await chromium.launch();
try {
  const page = await browser.newPage();
  await page.emulateMedia({ media: 'print' });
  await page.goto(pathToFileURL(path.join(dir, 'index.html')).href, { waitUntil: 'load' });
  await page.evaluate(() => document.fonts.ready);

  const overflowing = await page.$$eval('.page', (pages) =>
    pages.map((p, i) => ({ page: i + 1, over: p.scrollHeight - p.clientHeight })).filter((p) => p.over > 0)
  );
  if (overflowing.length) {
    throw new Error(`Content overflows: ${JSON.stringify(overflowing)}`);
  }

  await page.pdf({ path: output, preferCSSPageSize: true, printBackground: true });
  console.log(`Wrote ${path.relative(process.cwd(), output)}`);
} finally {
  await browser.close();
}
