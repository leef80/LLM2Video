// 情绪色卡台：build the whole film's palette from one mood with chroma.js.
//
// Every colour family gets an 11-step ramp on a shared OKLCH lightness ladder, so step k of any
// family has the same perceived lightness.  Dark steps drift toward the mood's shadow hue and
// light steps toward its light hue, which is what makes separate colours feel like one picture.
// Semantic roles (robe, skin, roof tile ...) point at ramp steps; required contrast pairs are
// checked and a failing role is walked along its ramp until it passes.
//
// Usage: node make_palette.mjs [out.json]   (default: ../llm2video/palette.json)
import chroma from "chroma-js";
import { writeFileSync } from "node:fs";

const MOOD = {
  name: "暮金宫阙",
  note: "申时夕照：暖金主光，紫墨阴影，空气里带一层米金薄雾",
  light: "#ffd8a0",   // key light colour: highlights lean here
  shadow: "#2b2342",  // shadow colour: shadows lean here
  lightPull: 0.32,    // how far the lightest step leans toward `light`
  shadowPull: 0.42,   // how far the darkest step leans toward `shadow`
};

// 0 = lightest (like 50), 10 = darkest (like 950)
const STEPS = 11;
const L_TOP = 0.965;
const L_BOTTOM = 0.2;
const FINE = 101; // dense ramp for continuous shading between steps
const ladderL = (pos) => L_TOP - (L_TOP - L_BOTTOM) * pos; // pos in 0..1

// base colours of each family, sampled from Ming palace architecture and costume
const FAMILIES = {
  ink: { base: "#2a211b", label: "墨", note: "发、眉、墨线" },
  iron: { base: "#3d4148", label: "铁", note: "盔、器" },
  vermilion: { base: "#a8291e", label: "朱", note: "宫墙、立柱、绯袍" },
  gold: { base: "#e3a82b", label: "金", note: "琉璃瓦、明黄龙袍" },
  jade: { base: "#2f7d62", label: "青绿", note: "斗拱、彩画" },
  lapis: { base: "#2b5786", label: "群青", note: "额枋、匾额、海水" },
  stone: { base: "#8e9ca3", label: "青石", note: "台阶" },
  marble: { base: "#e6e0d2", label: "汉白玉", note: "栏杆、须弥座" },
  pave: { base: "#a9a190", label: "金砖", note: "广场铺地" },
  bronze: { base: "#4f5a3e", label: "铜", note: "鼎" },
  skin: { base: "#efbd8f", label: "肤", note: "面、手" },
  wood: { base: "#6a4426", label: "木", note: "枪杆、格心" },
};

// semantic roles used by the renderer -> "family.step"
const ROLES = {
  "skin": "skin.2", "skin.shade": "skin.3", "skin.face.shade": "skin.2.5", "skin.blush": "vermilion.1.5", "ink": "ink.9", "hair": "ink.10",
  "mouth": "vermilion.9", "lip": "vermilion.7", "white": "marble.0", "teeth": "marble.1",
  "minister.robe": "vermilion.6", "minister.hat": "ink.10", "minister.hat.edge": "ink.8",
  "emperor.robe": "gold.3", "emperor.hat": "gold.4", "emperor.hat.dark": "gold.6",
  "trim.gold": "gold.4", "trim.gold.dark": "gold.7", "jade": "jade.1",
  "belt.minister": "vermilion.10", "belt.emperor": "vermilion.7", "belt.plaque": "gold.2",
  "badge.ground": "lapis.9", "badge.frame": "gold.5", "crane": "marble.0", "crane.crest": "vermilion.5",
  "dragon": "vermilion.7", "dragon.light": "vermilion.5", "pearl": "vermilion.5", "cloud.blue": "lapis.5",
  "wave.1": "lapis.6", "wave.2": "marble.1", "wave.3": "jade.5", "wave.4": "lapis.8", "rock.light": "gold.1",
  "boot": "ink.10",
  "guard.armor": "vermilion.8", "guard.trim": "gold.5", "guard.legs": "ink.9", "steel": "stone.2",
  "steel.dark": "iron.5", "helmet": "iron.7", "tassel": "vermilion.6", "spear": "wood.7",
  "hall.red": "vermilion.6", "hall.red.light": "vermilion.5", "hall.red.dark": "vermilion.8",
  "hall.door": "vermilion.7", "hall.door.panel": "vermilion.6", "hall.void": "vermilion.10",
  "hall.lattice.ground": "wood.8", "hall.lattice": "gold.5", "hall.base": "marble.1",
  "hall.base.light": "marble.0", "hall.base.dark": "marble.4",
  "roof.tile": "gold.4", "roof.tile.dark": "gold.7", "eave.under": "ink.9", "ornament.dark": "ink.8",
  "lintel.blue": "lapis.7", "lintel.green": "jade.6", "bracket.gap": "ink.9", "paint.gold": "gold.4",
  "plaque.frame": "gold.5", "plaque.ground": "lapis.9", "plaque.text": "gold.2", "plaque.stud": "gold.7",
  "steps": "stone.4", "marble": "marble.1", "terrace": "marble.2", "terrace.band": "marble.1",
  "terrace.dark": "marble.4", "terrace.panel": "marble.3", "spout": "marble.5", "spout.hole": "ink.8",
  "pave": "pave.3", "pave.path": "pave.2", "pave.grout": "pave.5", "pave.terrace": "pave.2",
  "ramp": "marble.3", "ramp.inner": "marble.2", "ramp.relief.hi": "marble.0", "ramp.relief.lo": "marble.6",
  "ramp.relief": "marble.2",
  "gate.wall": "vermilion.7", "gate.base": "pave.6", "gate.coping": "marble.2", "gate.void": "vermilion.10",
  "corridor.wall": "vermilion.7", "corridor.col": "vermilion.8", "corridor.window": "wood.9",
  "corridor.lattice": "gold.6", "corridor.roof": "gold.4", "corridor.roof.line": "gold.6",
  "corridor.roof.edge": "gold.6", "corridor.base": "pave.4",
  "bronze": "bronze.7", "bronze.dark": "bronze.9", "bronze.light": "bronze.5",
  "subtitle": "marble.0", "title": "marble.0", "title.glow": "ink.9", "seal": "vermilion.6",
  "seal.text": "marble.0", "smoke": "marble.1", "leaf": "gold.3", "leaf.vein": "gold.6", "bird": "ink.9",
};

// contrast the picture must keep: [foreground role, background role, min WCAG ratio, why]
// the foreground role is the one moved when a pair fails
const CHECKS = [
  ["subtitle", "#000000", 12, "字幕 / 黑边"],
  ["title", "title.glow", 7, "片名 / 暗晕"],
  ["ink", "skin", 7, "眉眼 / 皮肤"],
  ["mouth", "skin", 5, "张嘴 / 皮肤"],
  ["lip", "skin", 3, "唇线 / 皮肤"],
  ["skin.shade", "skin", 1.18, "脸部暗面可辨"],
  ["minister.robe", "pave", 2.6, "大臣 / 广场（图底）"],
  ["minister.robe", "steps", 2, "大臣 / 台阶"],
  ["minister.hat", "steps", 4.5, "乌纱帽 / 台阶"],
  ["emperor.robe", "hall.door", 3, "皇帝 / 殿门（图底）"],
  ["emperor.robe", "minister.robe", 3, "黄袍 / 绯袍"],
  ["crane", "badge.ground", 7, "仙鹤 / 补子"],
  ["badge.frame", "minister.robe", 2, "补子边 / 绯袍"],
  ["dragon", "emperor.robe", 3, "团龙 / 黄袍"],
  ["plaque.text", "plaque.ground", 7, "匾额字 / 匾心"],
  ["hall.lattice", "hall.lattice.ground", 3, "门窗格心"],
  ["roof.tile", "eave.under", 4.5, "瓦檐 / 檐下"],
  ["lintel.green", "lintel.blue", 1.25, "彩画青绿"],
  ["guard.armor", "pave", 2.6, "侍卫 / 广场（图底）"],
  ["marble", "steps", 1.8, "栏杆 / 台阶"],
  ["pave.path", "pave", 1.2, "御道 / 铺地"],
];

// ----------------------------------------------------------------------------- ramps

const lightHue = chroma(MOOD.light);
const shadowHue = chroma(MOOD.shadow);

function rampColor(base, pos) {
  const [Lb, Cb, Hb] = base.oklch();
  const L = ladderL(pos);
  const hb = Number.isNaN(Hb) ? 0 : Hb;
  // chroma peaks at the base lightness and tapers toward paper-white and ink-black
  const d = (L - Lb) / 0.55;
  let C = Cb * Math.max(0.18, 1 - 0.85 * d * d);
  if (L > 0.9) C *= 1 - (L - 0.9) * 6;
  let c = chroma.oklch(L, C, hb);
  // mood: shift hue toward light colour above the base, toward shadow colour below it
  if (L > Lb) c = chroma.mix(c, lightHue, MOOD.lightPull * ((L - Lb) / (L_TOP - Lb + 1e-6)) ** 1.3, "oklab");
  else c = chroma.mix(c, shadowHue, MOOD.shadowPull * ((Lb - L) / (Lb - L_BOTTOM + 1e-6)) ** 1.2, "oklab");
  // keep the ladder lightness exact, then pull chroma in until the colour fits sRGB
  let [, C2, H2] = c.oklch();
  if (Number.isNaN(H2)) H2 = hb;
  let out = chroma.oklch(L, C2, H2);
  for (let i = 0; i < 60 && out.clipped(); i++) {
    C2 *= 0.95;
    out = chroma.oklch(L, C2, H2);
  }
  return out;
}

const families = {};
for (const [name, f] of Object.entries(FAMILIES)) {
  const base = chroma(f.base);
  const fine = [];
  for (let i = 0; i < FINE; i++) fine.push(rampColor(base, i / (FINE - 1)));
  const steps = [];
  for (let k = 0; k < STEPS; k++) steps.push(fine[Math.round((k * (FINE - 1)) / (STEPS - 1))]);
  const baseStep = steps.reduce((bi, c, i) => (chroma.deltaE(c, base) < chroma.deltaE(steps[bi], base) ? i : bi), 0);
  families[name] = { ...f, baseStep, steps, fine };
}

const colorOf = (ref, roles) => {
  if (ref.startsWith("#")) return chroma(ref);
  const tok = roles[ref] ?? ref;
  const [fam, step] = tok.split(/\.(.+)/);
  const f = families[fam], x = Number(step) * (FINE - 1) / (STEPS - 1);
  return f.fine[Math.round(x)];
};

// ----------------------------------------------------------------------------- contrast audit

const roles = { ...ROLES };
const audit = [];
for (const [fg, bg, min, why] of CHECKS) {
  const before = roles[fg];
  let ratio = chroma.contrast(colorOf(fg, roles), colorOf(bg, roles));
  if (ratio < min) {
    const [fam, s0] = roles[fg].split(".");
    const darker = colorOf(fg, roles).oklch()[0] < colorOf(bg, roles).oklch()[0];
    let s = Number(s0);
    while (ratio < min && (darker ? s < STEPS - 1 : s > 0)) {
      s += darker ? 1 : -1;
      roles[fg] = `${fam}.${s}`;
      ratio = chroma.contrast(colorOf(fg, roles), colorOf(bg, roles));
    }
  }
  const apca = chroma.contrastAPCA(colorOf(fg, roles), colorOf(bg, roles));
  audit.push({ fg, bg, why, min, ratio: +ratio.toFixed(2), apca: +apca.toFixed(1), pass: ratio >= min,
               moved: before !== roles[fg] ? `${before} → ${roles[fg]}` : null });
}

// ----------------------------------------------------------------------------- sky, haze, specials

// sky by elevation angle: warm haze at the horizon through cream into a dusk blue
const skyScale = chroma
  .scale([chroma.mix(MOOD.light, families.gold.steps[1], 0.4, "oklab"), families.gold.steps[0],
          families.marble.steps[0], families.lapis.steps[2], families.lapis.steps[4], families.lapis.steps[6]])
  .domain([0, 4, 11, 24, 50, 90]).mode("oklab");
const skyStops = [-30, 0, 3, 9, 18, 32, 55, 90].map((e) => [e, skyScale(Math.max(0, e)).hex()]);
const below = chroma.mix(skyScale(0), families.pave.steps[3], 0.35, "oklab");
skyStops[0][1] = below.hex();

const special = {
  haze: chroma.mix(skyScale(2), families.marble.steps[1], 0.45, "oklab").hex(),
  glow: chroma.mix(MOOD.light, "#ffffff", 0.2, "oklab").hex(),
  rays: MOOD.light,
  shadow: MOOD.shadow,
  cloud: chroma.mix(families.marble.steps[0], MOOD.light, 0.25, "oklab").hex(),
};

// ----------------------------------------------------------------------------- write

const hex = (c) => c.hex();
const out = {
  mood: MOOD,
  ladder: Array.from({ length: STEPS }, (_, k) => +ladderL(k / (STEPS - 1)).toFixed(3)),
  families: Object.fromEntries(Object.entries(families).map(([n, f]) => [n, {
    label: f.label, note: f.note, base: f.base, baseStep: f.baseStep,
    steps: f.steps.map(hex), fine: f.fine.map(hex),
  }])),
  roles,
  sky: skyStops,
  special,
  audit,
};
const dst = process.argv[2] || new URL("../llm2video/palette.json", import.meta.url).pathname;
writeFileSync(dst, JSON.stringify(out, null, 1) + "\n");

console.log(`${MOOD.name}  ->  ${dst}`);
for (const [n, f] of Object.entries(families)) console.log(n.padEnd(10), f.steps.map(hex).join(" "));
console.log("\ncontrast audit");
for (const a of audit) {
  console.log(`${a.pass ? "ok  " : "FAIL"} ${a.why.padEnd(10)} ${String(a.ratio).padStart(5)} ≥ ${a.min}  APCA ${a.apca}` +
              (a.moved ? `   auto: ${a.moved}` : ""));
}
if (audit.some((a) => !a.pass)) process.exitCode = 1;
