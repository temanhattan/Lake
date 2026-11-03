const fs = require("node:fs");
const path = require("node:path");

const root = path.resolve(__dirname, "..");
const sampleRate = 48000;
const seconds = 52;
const samples = sampleRate * seconds;
const data = Buffer.alloc(samples * 2);
const events = [0.2, 3.2, 8.2, 12.2, 18.2, 26, 34.2, 41.2, 46.2];
for (let i = 0; i < samples; i += 1) {
  const time = i / sampleRate;
  let value = 0;
  for (const event of events) {
    const age = time - event;
    if (age >= 0 && age < 0.16) value += Math.sin(age * 2 * Math.PI * 220) * Math.exp(-age * 24) * 0.18;
  }
  data.writeInt16LE(Math.max(-1, Math.min(1, value)) * 32767, i * 2);
}
const header = Buffer.alloc(44);
header.write("RIFF", 0); header.writeUInt32LE(36 + data.length, 4); header.write("WAVE", 8);
header.write("fmt ", 12); header.writeUInt32LE(16, 16); header.writeUInt16LE(1, 20);
header.writeUInt16LE(1, 22); header.writeUInt32LE(sampleRate, 24);
header.writeUInt32LE(sampleRate * 2, 28); header.writeUInt16LE(2, 32); header.writeUInt16LE(16, 34);
header.write("data", 36); header.writeUInt32LE(data.length, 40);
fs.mkdirSync(path.join(root, "public"), { recursive: true });
fs.writeFileSync(path.join(root, "public", "sound-design.wav"), Buffer.concat([header, data]));
console.log("Generated original pen-pop sound design at nominal low gain.");
