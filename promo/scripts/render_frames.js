const path = require("node:path");
const { bundle } = require("@remotion/bundler");
const { renderFrames, selectComposition } = require("@remotion/renderer");
const { prepare } = require("./prepare_public");
require("./generate_sound_design");

async function main() {
  prepare();
  const root = path.resolve(__dirname, "..");
  const serveUrl = await bundle({ entryPoint: path.join(root, "src", "index.jsx"), webpackOverride: (config) => config });
  const composition = await selectComposition({ serveUrl, id: "LakePromoEN" });
  await renderFrames({
    serveUrl,
    composition,
    outputDir: path.join(root, "out", "frames"),
    imageFormat: "png",
    frames: [0, 90, 360, 540, 1020, 1230, 1500],
  });
  console.log("Rendered storyboard checkpoint frames.");
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
