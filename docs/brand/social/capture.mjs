#!/usr/bin/env node
/**
 * Render Pulse social boards to PNG via system Chrome.
 * Usage: node capture.mjs
 * Serves docs/brand over 127.0.0.1 so Google Fonts and stills load.
 */
import { createServer } from "node:http";
import { readFile, stat } from "node:fs/promises";
import { extname, join, dirname } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const puppeteer = require("puppeteer-core");

const ROOT = dirname(fileURLToPath(import.meta.url));
const BRAND = join(ROOT, "..");
const CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";

const TYPES = {
  ".html": "text/html; charset=utf-8",
  ".png": "image/png",
  ".svg": "image/svg+xml",
  ".css": "text/css",
  ".js": "text/javascript",
};

const BOARDS = [
  ["avatar-ink", "evorove-avatar.png"],
  ["avatar-cream", "evorove-avatar-cream.png"],
  ["avatar-coral", "evorove-avatar-coral.png"],
  ["avatar-lockup", "evorove-avatar-lockup.png"],
  ["app-icon", "evorove-app-icon.png"],
  ["linkedin", "evorove-linkedin-banner.png"],
  ["xheader", "evorove-x-header.png"],
  ["youtube", "evorove-youtube-banner.png"],
  ["og", "evorove-og.png"],
  ["post-inquiry", "evorove-post-inquiry-cycle.png"],
  ["post-cycle", "evorove-post-capture-vs-cycle.png"],
  ["post-engine", "evorove-post-engine-decides.png"],
  ["post-dna", "evorove-post-same-dna.png"],
  ["post-chat", "evorove-post-not-a-chat.png"],
  ["post-dead", "evorove-post-dead-air.png"],
  ["post-follow", "evorove-post-follow-up.png"],
  ["post-building", "evorove-post-building.png"],
  ["ig", "evorove-ig-square.png"],
  ["story-line", "evorove-story-line.png"],
  ["story-orbit", "evorove-story-orbit.png"],
  ["story-cycle", "evorove-story-cycle.png"],
  ["story-unfinished", "evorove-story-unfinished.png"],
];

function server() {
  return createServer(async (req, res) => {
    const url = new URL(req.url, "http://127.0.0.1");
    let rel = decodeURIComponent(url.pathname);
    if (rel === "/") rel = "/evorove-pulse-brandbook.html";
    const file = join(BRAND, rel.replace(/^\/+/, ""));
    if (!file.startsWith(BRAND)) {
      res.writeHead(403);
      res.end();
      return;
    }
    try {
      const info = await stat(file);
      if (!info.isFile()) throw new Error("not file");
      const body = await readFile(file);
      res.writeHead(200, { "content-type": TYPES[extname(file)] || "application/octet-stream" });
      res.end(body);
    } catch {
      res.writeHead(404);
      res.end("not found");
    }
  });
}

const srv = server();
await new Promise((resolve) => srv.listen(0, "127.0.0.1", resolve));
const { port } = srv.address();
const origin = `http://127.0.0.1:${port}`;

const browser = await puppeteer.launch({
  executablePath: CHROME,
  headless: true,
  args: ["--hide-scrollbars", "--disable-gpu", "--font-render-hinting=none"],
});

try {
  const page = await browser.newPage();
  await page.setViewport({ width: 2560, height: 1920, deviceScaleFactor: 1 });
  const only = new Set(process.argv.slice(2));
  for (const [id, filename] of BOARDS) {
    if (only.size && !only.has(id) && !only.has(filename)) continue;
    const dest = join(ROOT, filename);
    await page.goto(`${origin}/social/boards.html?board=${id}`, { waitUntil: "networkidle0", timeout: 60000 });
    await page.evaluate(() => document.fonts.ready);
    await new Promise((r) => setTimeout(r, 400));
    const board = await page.$(".board.is-on");
    if (!board) throw new Error(`missing board ${id}`);
    await board.screenshot({ path: dest, type: "png", omitBackground: false });
    const box = await board.boundingBox();
    console.log(`wrote ${filename}  ${Math.round(box.width)}×${Math.round(box.height)}`);
  }
} finally {
  await browser.close();
  srv.close();
}
