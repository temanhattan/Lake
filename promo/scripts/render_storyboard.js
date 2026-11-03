/** Render storyboard.svg to a 2x review PNG. */
const fs = require("node:fs");
const path = require("node:path");
const { chromium } = require("playwright");

const root = path.resolve(__dirname, "..", "..");
const source = path.join(root, "promo", "storyboard.svg");
const output = path.join(root, "promo", "storyboard.png");

async function main() {
  const svg = fs.readFileSync(source, "utf8");
  const encoded = Buffer.from(svg).toString("base64");
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({
    viewport: { width: 1600, height: 1080 },
    deviceScaleFactor: 2,
  });
  await page.setContent(
    '<style>html,body{margin:0;padding:0}</style>' +
      `<img id="storyboard" width="1600" height="1080" src="data:image/svg+xml;base64,${encoded}">`,
    { waitUntil: "load" },
  );
  await page.locator("#storyboard").evaluate((image) => image.decode());
  await page.screenshot({ path: output, fullPage: true });
  await browser.close();
  console.log(`${path.relative(root, output)} · ${fs.statSync(output).size} bytes`);
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
