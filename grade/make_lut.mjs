// Build colour-grading 3D LUTs (.cube) with chroma.js, working in perceptual OKLab/OKLCH space.
// Usage: node make_lut.mjs [outDir]   ->  writes one <look>.cube per look below.
// Apply with ffmpeg:  ffmpeg -i in.mp4 -vf lut3d=dusk.cube -c:a copy out.mp4
import chroma from "chroma-js";
import { writeFileSync, mkdirSync } from "node:fs";
import { join } from "node:path";

const N = 33; // LUT resolution per axis

const smooth = (a, b, x) => {
  const t = Math.min(1, Math.max(0, (x - a) / (b - a)));
  return t * t * (3 - 2 * t);
};

// S-curve on lightness around a pivot, strength k (0 = none)
const contrast = (L, k, pivot = 0.55) => {
  const s = (x) => 1 / (1 + Math.exp(-k * (x - pivot)));
  return k ? (s(L) - s(0)) / (s(1) - s(0)) : L;
};

// hue distance in degrees
const hueDist = (a, b) => Math.abs(((a - b + 540) % 360) - 180);

const LOOKS = {
  // 暮金：夕照鎏金。暗部压到暖褐，高光偏金，红黄更浓，蓝天收一点
  dusk: {
    shadows: "#3a1c10", highlights: "#ffcf7a", shadowAmt: 0.32, highAmt: 0.28,
    contrast: 6.0, sat: 1.14, warmBoost: 0.18, coolCut: 0.3, lift: 0.01,
  },
  // 青橙：电影常见的青橙对比。暗部青、亮部橙，肤色和金色保留
  teal_orange: {
    shadows: "#06505e", highlights: "#ffa95e", shadowAmt: 0.5, highAmt: 0.2,
    contrast: 7.0, sat: 1.1, warmBoost: 0.1, coolCut: -0.35, lift: 0.0,
  },
  // 宣纸：旧画卷质感。降饱和、黑位抬成墨色、高光偏米黄、反差变柔
  xuanzhi: {
    shadows: "#3b3228", highlights: "#f3e6c8", shadowAmt: 0.35, highAmt: 0.22,
    contrast: -1.0, sat: 0.72, warmBoost: 0.0, coolCut: 0.25, lift: 0.06,
  },
};

function grade(rgb, p) {
  let c = chroma.gl(rgb[0], rgb[1], rgb[2]);
  let [L, C, H] = c.oklch();
  if (Number.isNaN(H)) H = 0;

  // pure black (letterbox bars) stays black: fade every adjustment in above L≈0.05
  const keep = smooth(0.02, 0.08, L);
  const L0 = L;
  // tone curve on perceptual lightness, then black lift
  L = p.contrast >= 0 ? contrast(L, p.contrast) : 0.08 + L * 0.86; // negative = flatten
  L = p.lift + L * (1 - p.lift);

  // hue-selective saturation: warm hues (reds/golds ~20-90°) boosted, blues (~230-260°) trimmed
  let sat = p.sat;
  sat *= 1 + p.warmBoost * (1 - smooth(25, 60, hueDist(H, 60)));
  sat *= 1 - p.coolCut * (1 - smooth(20, 55, hueDist(H, 245)));
  C *= sat;

  c = chroma.oklch(L0 + (L - L0) * keep, C, H);

  // split toning, weighted by lightness, mixed in OKLab so it stays even
  const wShadow = keep * p.shadowAmt * (1 - smooth(0.15, 0.6, L));
  const wHigh = p.highAmt * smooth(0.45, 0.95, L);
  if (wShadow > 0) c = chroma.mix(c, p.shadows, wShadow, "oklab");
  if (wHigh > 0) c = chroma.mix(c, p.highlights, wHigh, "oklab");

  return c.gl().slice(0, 3).map((v) => Math.min(1, Math.max(0, v)));
}

const out = process.argv[2] || ".";
mkdirSync(out, { recursive: true });
for (const [name, p] of Object.entries(LOOKS)) {
  const lines = [`TITLE "${name}"`, `LUT_3D_SIZE ${N}`, "DOMAIN_MIN 0 0 0", "DOMAIN_MAX 1 1 1"];
  // .cube order: red changes fastest, then green, then blue
  for (let b = 0; b < N; b++)
    for (let g = 0; g < N; g++)
      for (let r = 0; r < N; r++) {
        const v = grade([r / (N - 1), g / (N - 1), b / (N - 1)], p);
        lines.push(v.map((x) => x.toFixed(6)).join(" "));
      }
  writeFileSync(join(out, `${name}.cube`), lines.join("\n") + "\n");
  console.log("wrote", join(out, `${name}.cube`));
}
