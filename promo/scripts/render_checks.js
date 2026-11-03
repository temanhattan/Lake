const path = require("node:path");
const { bundle } = require("@remotion/bundler");
const { renderFrames, selectComposition } = require("@remotion/renderer");
const { prepare } = require("./prepare_public");

async function main() {
  prepare();
  const root = path.resolve(__dirname, "..");
  const serveUrl = await bundle({ entryPoint: path.join(root, "src", "index.jsx"), webpackOverride: (config) => config });
  const composition = await selectComposition({ serveUrl, id: "LakePromoAR" });
  await renderFrames({
    serveUrl,
    composition,
    outputDir: path.join(root, "out", "checks"),
    imageFormat: "png",
    frames: [60, 810, 1050, 1410],
  });
  console.log("Rendered Arabic caption verification frames.");
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
