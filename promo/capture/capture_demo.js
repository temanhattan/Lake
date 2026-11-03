/** Capture the fictional Lake demo flow for later scene compositing. */
const fs = require("node:fs");
const path = require("node:path");
const { spawn } = require("node:child_process");
const { chromium } = require("playwright");

const root = path.resolve(__dirname, "..", "..");
const output = path.join(root, "promo", "captures");
const metadataPath = path.join(output, "capture.json");
const python = process.env.PYTHON || "python3.12";

function waitForServer(child) {
  return new Promise((resolve, reject) => {
    let buffer = "";
    const onData = (chunk) => {
      buffer += chunk.toString();
      const match = buffer.match(/http:\/\/127\.0\.0\.1:\d+/);
      if (match) resolve(match[0]);
    };
    child.stdout.on("data", onData);
    child.stderr.on("data", (chunk) => process.stderr.write(chunk));
    child.once("error", reject);
    child.once("exit", (code) => reject(new Error(`fixture server exited with ${code}`)));
  });
}

async function main() {
  fs.mkdirSync(output, { recursive: true });
  const server = spawn(python, ["promo/capture/capture_server.py"], {
    cwd: root,
    stdio: ["ignore", "pipe", "pipe"],
  });
  let browser;
  try {
    const origin = await waitForServer(server);
    browser = await chromium.launch({ headless: true });
    const context = await browser.newContext({
      viewport: { width: 1440, height: 900 },
      deviceScaleFactor: 2,
      reducedMotion: "no-preference",
    });
    await context.addInitScript(() => {
      localStorage.setItem("lake-demo-mode", "1");
      localStorage.setItem("lake-motion", "full");
      sessionStorage.clear();
    });
    const page = await context.newPage();
    const requests = [];
    page.on("request", (request) => requests.push(request.url()));
    await page.goto(`${origin}/welcome`, { waitUntil: "networkidle" });
    await page.locator("#welcome-demo-toggle").waitFor();
    if (!(await page.locator("#welcome-demo-toggle").isChecked())) {
      throw new Error("demo mode did not initialize enabled");
    }
    await page.screenshot({ path: path.join(output, "01-welcome.png"), fullPage: true });

    await page.locator("#welcome-start").click();
    await page.locator("#search").waitFor({ state: "visible" });
    await page.waitForTimeout(500);
    await page.screenshot({ path: path.join(output, "02-library.png"), fullPage: true });

    await page.locator("#mode").selectOption("keyword");
    await page.locator("#search").fill("fictional local");
    await page.waitForTimeout(800);
    if (await page.locator(".tile[data-id]").count() === 0) {
      throw new Error(`search produced no result: ${await page.locator("#results").innerText()}`);
    }
    await page.locator(".tile[data-id]").first().waitFor();
    await page.screenshot({ path: path.join(output, "03-search.png"), fullPage: true });

    await page.locator(".tile[data-id]").first().click();
    await page.locator("#reader").waitFor({ state: "visible" });
    await page.locator('[data-act="context"]').waitFor();
    await page.screenshot({ path: path.join(output, "04-chat.png"), fullPage: true });
    await page.locator('[data-act="context"]').click();
    await page.waitForTimeout(500);
    await page.screenshot({ path: path.join(output, "05-context.png"), fullPage: true });

    const external = requests.filter((url) => !url.startsWith(`${origin}/`));
    if (external.length) throw new Error(`non-local capture request: ${external[0]}`);
    const metadata = {
      demoMode: true,
      fixtureOnly: true,
      origin,
      deviceScaleFactor: 2,
      viewport: { width: 1440, height: 900 },
      screenshots: ["01-welcome.png", "02-library.png", "03-search.png", "04-chat.png", "05-context.png"],
      requests: [...new Set(requests.map((url) => new URL(url).pathname))].sort(),
      externalRequests: external,
    };
    fs.writeFileSync(metadataPath, `${JSON.stringify(metadata, null, 2)}\n`);
    await context.close();
  } finally {
    if (browser) await browser.close();
    server.kill();
  }
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
