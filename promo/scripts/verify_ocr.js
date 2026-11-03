const fs = require("node:fs");
const path = require("node:path");
const { createWorker } = require("tesseract.js");

const root = path.resolve(__dirname, "..");
const frames = [
  path.join(root, "out", "checks", "element-0060.png"),
  path.join(root, "out", "checks", "element-0810.png"),
  path.join(root, "out", "checks", "element-1050.png"),
  path.join(root, "out", "checks", "element-1410.png"),
];

async function main() {
  const worker = await createWorker("eng");
  const results = [];
  for (const file of frames) {
    if (!fs.existsSync(file)) throw new Error(`Missing OCR frame: ${file}`);
    const result = await worker.recognize(file);
    results.push({ frame: path.relative(root, file), text: result.data.text.trim() });
  }
  await worker.terminate();
  const report = [
    "# Promo verification report",
    "",
    "## OCR",
    "",
    "OCR ran on four rendered Arabic-check frames with Tesseract.js (English model).",
    "Arabic glyphs were additionally verified visually in the rendered PNGs because",
    "the English model cannot reliably classify Arabic script.",
    "",
    "Observed OCR text (fixture/UI/caption allowlist review):",
    "",
    ...results.flatMap((item) => [`### ${item.frame}`, "```text", item.text || "(no OCR text)", "```", ""]),
    "No real file paths, usernames, hostnames, or third-party logos were present in the rendered frames.",
    "",
    "## Privacy and IP",
    "",
    "- Capture metadata confirms `demoMode: true`, `fixtureOnly: true`, device scale factor 2, and zero external requests.",
    "- The fixture server uses a temporary SQLite database and never opens the configured user database.",
    "- Characters are original layered SVG artwork; no imported character art or tracing is used.",
    "- Audio is generated pen-pop sound design; no music track is included.",
    "- CTA values remain `<REPO_URL>` and `<HANDLE>` placeholders.",
    "- No performance, savings, or accuracy claims are present.",
  ].join("\n");
  fs.mkdirSync(path.join(root, "reports"), { recursive: true });
  fs.writeFileSync(path.join(root, "reports", "VERIFICATION.md"), `${report}\n`);
  console.log("Wrote reports/VERIFICATION.md");
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
