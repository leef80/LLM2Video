// Compare how chroma.js blends the film's typical colour pairs in each colour space.
// Usage: node mix_compare.mjs [palette.json] > mixes.json
import chroma from "chroma-js";
import { readFileSync } from "node:fs";

const P = JSON.parse(readFileSync(process.argv[2] || new URL("../llm2video/palette.json", import.meta.url), "utf8"));
const step = (tok) => {
  const [f, k] = tok.split(".");
  return P.families[f].steps[Number(k)];
};

const PAIRS = [
  ["朱墙 → 紫墨阴影", step("vermilion.6"), P.mood.shadow],
  ["琉璃金 → 暖金主光", step("gold.4"), P.mood.light],
  ["朱墙 → 远处薄雾", step("vermilion.6"), P.special.haze],
  ["肤色 → 紫墨阴影", step("skin.2"), P.mood.shadow],
  ["琉璃金 → 群青天", step("gold.3"), step("lapis.5")],
  ["青绿 → 朱红", step("jade.5"), step("vermilion.5")],
];
const MODES = ["rgb", "lab", "lch", "oklab", "oklch"];
const N = 9;

const out = PAIRS.map(([name, a, b]) => ({
  name, a, b,
  modes: Object.fromEntries(MODES.map((m) => {
    const cols = chroma.scale([a, b]).mode(m).colors(N, null);
    return [m, { hex: cols.map((c) => c.hex()), chroma: cols.map((c) => +c.oklch()[1].toFixed(3)) }];
  })),
}));
console.log(JSON.stringify(out));
