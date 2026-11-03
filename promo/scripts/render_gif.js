const fs = require("node:fs");
const path = require("node:path");
const { bundle } = require("@remotion/bundler");
const { renderMedia, selectComposition } = require("@remotion/renderer");
const { prepare } = require("./prepare_public");

async function main() {
  prepare();
  const root = path.resolve(__dirname, "..");
  const serveUrl = await bundle({ entryPoint: path.join(root, "src", "index.jsx"), webpackOverride: (config) => config });
  const composition = await selectComposition({ serveUrl, id: "LakePromoGif" });
  const output = path.join(root, "out", "lake-readme.gif");
  await renderMedia({ serveUrl, composition, codec: "gif", outputLocation: output });
  const size = fs.statSync(output).size;
  if (size >= 8 * 1024 * 1024) throw new Error(`README GIF is ${size} bytes; expected under 8 MiB`);
  console.log(`Rendered lake-readme.gif · ${size} bytes`);
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
