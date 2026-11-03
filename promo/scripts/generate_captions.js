const fs = require("node:fs");
const path = require("node:path");

const root = path.resolve(__dirname, "..");
const script = JSON.parse(fs.readFileSync(path.join(root, "script.json"), "utf8"));
const captionsDir = path.join(root, "captions");
fs.mkdirSync(captionsDir, { recursive: true });

function stamp(seconds) {
  const whole = Math.floor(seconds);
  const hours = Math.floor(whole / 3600);
  const minutes = Math.floor((whole % 3600) / 60);
  const secs = whole % 60;
  const millis = Math.round((seconds - whole) * 1000);
  return `${String(hours).padStart(2, "0")}:${String(minutes).padStart(2, "0")}:${String(secs).padStart(2, "0")},${String(millis).padStart(3, "0")}`;
}

for (const language of ["en", "ar"]) {
  let index = 1;
  const entries = [];
  for (const scene of script.scenes) {
    for (const caption of scene.captions[language]) {
      entries.push(`${index++}\n${stamp(caption.start)} --> ${stamp(caption.end)}\n${caption.text}\n`);
    }
  }
  fs.writeFileSync(path.join(captionsDir, `${language}.srt`), `${entries.join("\n")}\n`);
}
console.log("Generated captions/en.srt and captions/ar.srt.");
