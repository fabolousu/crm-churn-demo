#!/usr/bin/env node
/**
 * D1 gate — accessibility (axe-core) + rendered broken-link crawl for the built SPA.
 *
 * What it does
 *   1. serves `web/dist/` on a free local port with SPA fallback;
 *   2. drives the installed Chrome/Edge through `playwright-core` (no browser download);
 *   3. for every reachable route: runs axe-core with the WCAG 2.0/2.1 A+AA rule tags,
 *      records broken same-origin links and any subresource that answers >= 400;
 *   4. exits 1 when a serious/critical axe violation, a broken link, or a failed
 *      subresource is found; exits 0 otherwise.
 *
 * Usage
 *   pnpm --dir web build
 *   pnpm --dir web check:ui
 *
 * Environment
 *   CHECK_UI_CHROME     explicit browser executable (default: autodetect Chrome/Edge)
 *   CHECK_UI_MAX_PAGES  crawl cap (default 40)
 *   CHECK_UI_STRICT=1   fail on every axe impact, not only serious/critical
 *
 * This is intentionally dependent on a real browser: the app is client-rendered, so a
 * static HTML crawler would see no links and report a false pass.
 */

import { createServer } from "node:http";
import { existsSync } from "node:fs";
import { readFile } from "node:fs/promises";
import { createRequire } from "node:module";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright-core";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const DIST = path.resolve(HERE, "..", "dist");
const INDEX = path.join(DIST, "index.html");
const MAX_PAGES = Number(process.env.CHECK_UI_MAX_PAGES ?? 40);
const STRICT = process.env.CHECK_UI_STRICT === "1";
const AXE_TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"];
const BLOCKING_IMPACTS = STRICT
  ? new Set(["minor", "moderate", "serious", "critical"])
  : new Set(["serious", "critical"]);

const MIME = {
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".mjs": "text/javascript; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".svg": "image/svg+xml",
  ".png": "image/png",
  ".jpg": "image/jpeg",
  ".jpeg": "image/jpeg",
  ".webp": "image/webp",
  ".ico": "image/x-icon",
  ".woff": "font/woff",
  ".woff2": "font/woff2",
  ".ttf": "font/ttf",
};

function axeScriptPath() {
  const require = createRequire(import.meta.url);
  const main = require.resolve("axe-core"); // .../axe-core/axe.js
  return path.join(path.dirname(main), "axe.min.js");
}

async function serveDist() {
  if (!existsSync(INDEX)) {
    throw new Error(`No production build at ${DIST}. Run: pnpm --dir web build`);
  }
  const server = createServer(async (req, res) => {
    try {
      const pathname = decodeURIComponent(new URL(req.url, "http://localhost").pathname);
      if (pathname === "/favicon.ico") {
        res.writeHead(204).end();
        return;
      }
      const resolved = path.resolve(DIST, "." + pathname);
      const inside = resolved === DIST || resolved.startsWith(DIST + path.sep);
      let file = pathname === "/" ? INDEX : inside ? resolved : null;
      if (file && !existsSync(file)) {
        // SPA fallback for extensionless routes; real assets must 404.
        file = path.extname(pathname) ? null : INDEX;
      }
      if (!file) {
        res.writeHead(404, { "content-type": "text/plain" }).end("not found");
        return;
      }
      const data = await readFile(file);
      res.writeHead(200, {
        "content-type": MIME[path.extname(file).toLowerCase()] ?? "application/octet-stream",
      });
      res.end(data);
    } catch {
      if (!res.headersSent) {
        res.writeHead(404, { "content-type": "text/plain" }).end("not found");
      } else {
        res.destroy();
      }
    }
  });
  await new Promise((resolve, reject) => {
    server.once("error", reject);
    server.listen(0, "127.0.0.1", resolve);
  });
  const { port } = server.address();
  return { server, base: `http://127.0.0.1:${port}` };
}

function browserCandidates() {
  const win = [
    process.env.CHECK_UI_CHROME,
    "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
    "C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe",
    "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
    "C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe",
  ];
  const posix = [
    process.env.CHECK_UI_CHROME,
    "/usr/bin/google-chrome",
    "/usr/bin/google-chrome-stable",
    "/usr/bin/chromium",
    "/usr/bin/chromium-browser",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
  ];
  return (process.platform === "win32" ? win : posix).filter(Boolean);
}

async function launchBrowser() {
  const args = ["--force-color-profile=srgb", "--disable-lcd-text"];
  let lastError;
  for (const executablePath of browserCandidates()) {
    if (!existsSync(executablePath)) continue;
    try {
      return await chromium.launch({ executablePath, headless: true, args });
    } catch (error) {
      lastError = error;
    }
  }
  for (const channel of ["chrome", "msedge"]) {
    try {
      return await chromium.launch({ channel, headless: true, args });
    } catch (error) {
      lastError = error;
    }
  }
  try {
    return await chromium.launch({ headless: true, args });
  } catch (error) {
    lastError = error;
  }
  throw new Error(
    `No Chrome/Edge found. Set CHECK_UI_CHROME to a browser executable, or run ` +
      `"pnpm --dir web exec playwright install chromium". Last error: ${lastError?.message}`
  );
}

function sameOriginTarget(href, pageUrl, origin) {
  let url;
  try {
    url = new URL(href, pageUrl);
  } catch {
    return null;
  }
  if (!/^https?:$/.test(url.protocol) || url.origin !== origin) return null;
  url.hash = "";
  return url.pathname || "/";
}

async function main() {
  const { server, base } = await serveDist();
  const origin = new URL(base).origin;
  const browser = await launchBrowser();
  const results = {
    visited: [],
    axe: [],
    broken: [],
    failedResources: [],
    consoleErrors: [],
  };

  try {
    const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
    const page = await context.newPage();
    let currentRoute = "/";

    page.on("pageerror", (error) => {
      results.consoleErrors.push({ route: currentRoute, text: `pageerror: ${error.message}` });
    });
    page.on("console", (message) => {
      if (message.type() === "error") {
        const text = message.text();
        if (!/favicon/i.test(text)) results.consoleErrors.push({ route: currentRoute, text });
      }
    });
    page.on("response", (response) => {
      if (response.status() >= 400 && response.url().startsWith(base)) {
        results.failedResources.push({
          route: currentRoute,
          status: response.status(),
          url: response.url().slice(base.length),
        });
      }
    });

    const axePath = axeScriptPath();
    const queue = ["/", "/act", "/portfolio"];
    const seen = new Set();

    while (queue.length > 0 && seen.size < MAX_PAGES) {
      const route = queue.shift();
      if (seen.has(route)) continue;
      seen.add(route);
      currentRoute = route;
      const pageUrl = new URL(route, base).href;

      let response;
      try {
        response = await page.goto(pageUrl, { waitUntil: "load", timeout: 25000 });
      } catch (error) {
        results.broken.push({ route, reason: `navigation failed: ${error.message}` });
        continue;
      }
      results.visited.push(route);
      await page.waitForTimeout(400);

      const status = response?.status() ?? 0;
      if (status >= 400) results.broken.push({ route, reason: `HTTP ${status}` });

      const bodyText = await page.evaluate(() => document.body?.innerText ?? "");
      if (route !== "/" && bodyText.includes("That screen is not in the demo")) {
        results.broken.push({ route, reason: "renders the NotFound screen" });
      }

      try {
        await page.addScriptTag({ path: axePath });
        const outcome = await page.evaluate(async (tags) => {
          await document.fonts.ready;
          return window.axe.run(document, { runOnly: { type: "tag", values: tags } });
        }, AXE_TAGS);
        for (const violation of outcome.violations) {
          results.axe.push({
            route,
            id: violation.id,
            impact: violation.impact,
            help: violation.help,
            nodes: violation.nodes.slice(0, 3).map((node) => node.target.join(" ")),
            count: violation.nodes.length,
          });
        }
      } catch (error) {
        results.axe.push({
          route,
          id: "axe-run-error",
          impact: "critical",
          help: error.message,
          nodes: [],
          count: 0,
        });
      }

      const hrefs = await page.$$eval("a[href]", (anchors) =>
        anchors.map((anchor) => anchor.getAttribute("href"))
      );
      for (const href of hrefs) {
        const target = sameOriginTarget(href, pageUrl, origin);
        if (target && !seen.has(target)) queue.push(target);
      }
    }
  } finally {
    await browser.close();
    await new Promise((resolve) => server.close(resolve));
  }

  const blocking = results.axe.filter((finding) => BLOCKING_IMPACTS.has(finding.impact));
  const passed =
    blocking.length === 0 && results.broken.length === 0 && results.failedResources.length === 0;

  console.log(`\nD1 UI check — ${base}`);
  console.log(`Visited ${results.visited.length} route(s): ${results.visited.join(", ")}`);

  if (results.axe.length === 0) {
    console.log("axe: no violations");
  } else {
    console.log(`axe: ${results.axe.length} violation(s) — ${blocking.length} blocking`);
    for (const violation of results.axe) {
      const mark = BLOCKING_IMPACTS.has(violation.impact) ? "BLOCK" : "note ";
      console.log(`  [${mark}] ${violation.impact} ${violation.id} on ${violation.route} (${violation.count} node(s))`);
      console.log(`         ${violation.help}`);
      for (const node of violation.nodes) console.log(`         target: ${node}`);
    }
  }

  if (results.broken.length === 0) {
    console.log("broken links: none");
  } else {
    console.log(`broken links: ${results.broken.length}`);
    for (const link of results.broken) console.log(`  ${link.route} — ${link.reason}`);
  }

  if (results.failedResources.length === 0) {
    console.log("failed subresources: none");
  } else {
    console.log(`failed subresources: ${results.failedResources.length}`);
    for (const resource of results.failedResources) {
      console.log(`  on ${resource.route}: HTTP ${resource.status} ${resource.url}`);
    }
  }

  if (results.consoleErrors.length > 0) {
    console.log(`console errors (non-blocking): ${results.consoleErrors.length}`);
    for (const entry of results.consoleErrors.slice(0, 10)) {
      console.log(`  on ${entry.route}: ${entry.text}`);
    }
  }

  console.log(passed ? "\nPASS" : "\nFAIL");
  process.exitCode = passed ? 0 : 1;
}

main().catch((error) => {
  console.error(`check-ui failed: ${error.message}`);
  process.exitCode = 1;
});
