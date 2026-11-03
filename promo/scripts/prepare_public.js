const fs = require("node:fs");
const path = require("node:path");

const root = path.resolve(__dirname, "..");
const publicDir = path.join(root, "public");
const captureDir = path.join(publicDir, "captures");
function prepare() {
  fs.mkdirSync(captureDir, { recursive: true });
  for (const name of ["01-welcome.png", "02-library.png", "03-search.png", "04-chat.png", "05-context.png"]) {
    const source = path.join(root, "captures", name);
    if (!fs.existsSync(source)) throw new Error(`Missing capture ${source}; run npm run capture:demo first`);
    fs.copyFileSync(source, path.join(captureDir, name));
  }
  for (const name of ["dm-sans.woff2", "arabic.woff2"]) {
    const source = path.join(root, "..", "lake", "static", "fonts", name);
    if (!fs.existsSync(source)) throw new Error(`Missing OFL font ${source}`);
    fs.copyFileSync(source, path.join(publicDir, name));
  }
  console.log("Prepared Remotion public captures.");
}

module.exports = { prepare };
