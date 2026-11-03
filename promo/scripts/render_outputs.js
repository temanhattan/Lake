const fs = require("node:fs");
const path = require("node:path");
const { bundle } = require("@remotion/bundler");
const { renderMedia, selectComposition } = require("@remotion/renderer");
const { prepare } = require("./prepare_public");
require("./generate_sound_design");

async function render(serveUrl, root, id, outputName) {
  const composition = await selectComposition({ serveUrl, id });
  const output = path.join(root, "out", outputName);
  fs.mkdirSync(path.dirname(output), { recursive: true });
  await renderMedia({ serveUrl, composition, codec: "h264", outputLocation: output });
  console.log(`Rendered ${outputName}`);
}

async function main() {
  prepare();
  const root = path.resolve(__dirname, "..");
  const serveUrl = await bundle({ entryPoint: path.join(root, "src", "index.jsx"), webpackOverride: (config) => config });
  await render(serveUrl, root, "LakePromoEN", "lake-master-en.mp4");
  await render(serveUrl, root, "LakePromoAR", "lake-master-ar.mp4");
  await render(serveUrl, root, "LakePromo16x9", "lake-16x9-en.mp4");
  await render(serveUrl, root, "LakePromoTeaser", "lake-teaser-15s.mp4");
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
