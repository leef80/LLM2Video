// 20 mood presets for the palette generator: node make_palette.mjs out.json --preset=07
//
// Each preset changes the mood (key light / shadow colour and how hard they pull), optionally
// re-bases a few colour families and scales overall saturation.  Everything else (ladder,
// roles, contrast audit) is shared, so the versions stay comparable.
// Trend and product colours are approximations from public announcements (see docs/color_research.md).

const base = { space: "oklch", maxHue: 20, sat: 1, lightPull: 0.32, shadowPull: 0.42 };

export const PRESETS = [
  // ---------------------------------------------------------------- 国际流行色机构
  { id: "01", group: "流行色", name: "云舞白", source: "Pantone 2026 年度色 Cloud Dancer 11-4201",
    note: "高调、轻盈、低饱和，像薄雾里的宫殿", light: "#f0eee9", shadow: "#3b4250",
    lightPull: 0.45, shadowPull: 0.35, sat: 0.72, families: { marble: "#f0eee9", pave: "#c4beb2" } },
  { id: "02", group: "流行色", name: "蜕变青", source: "WGSN × Coloro 2026 年度色 Transformative Teal",
    note: "阴影沉入青绿，暖米高光", light: "#fbe7c6", shadow: "#0f3d3c", families: { lapis: "#1f6a72" } },
  { id: "03", group: "流行色", name: "夜光蓝", source: "WGSN × Coloro 2027 年度色 Luminous Blue",
    note: "蓝调时刻，冷光照金瓦", light: "#d6e2ff", shadow: "#152a66", lightPull: 0.4,
    families: { lapis: "#2b4fae" } },
  { id: "04", group: "流行色", name: "能量橙 · 黏土", source: "WGSN SS27 Energy Orange / Clay",
    note: "落日橙光，黏土色阴影", light: "#ffb070", shadow: "#4a2c22", lightPull: 0.4 },
  { id: "05", group: "流行色", name: "蜡纸 · 可可", source: "WGSN AW26/27 Wax Paper / Cocoa Powder",
    note: "旧纸与可可，低饱和怀旧", light: "#f1e4bf", shadow: "#3d2a22", sat: 0.78, shadowPull: 0.5 },
  { id: "06", group: "流行色", name: "鲜紫 · 绿光", source: "WGSN AW26/27 Fresh Purple / Green Glow",
    note: "紫色阴影对荧光绿高光，戏剧化", light: "#e4ffb3", shadow: "#3a1f66", lightPull: 0.36,
    shadowPull: 0.5 },
  { id: "07", group: "流行色", name: "赤褐 · 丁香", source: "WGSN AW27/28 Russet / Peaceful Lilac",
    note: "丁香色天光，赤褐暗部", light: "#e7ddff", shadow: "#4a2216", lightPull: 0.4 },
  { id: "08", group: "流行色", name: "玉米黄 · 深绿", source: "WGSN AW27/28 Maize / Deep Green",
    note: "玉米黄阳光，墨绿阴影", light: "#ffe08a", shadow: "#10302a", families: { jade: "#1d6b4f" } },
  { id: "09", group: "流行色", name: "流行粉 · 草甸", source: "WGSN SS27 Pop Pink / Meadowland Green",
    note: "春日粉光，草绿阴影，柔和轻快", light: "#ffd3e4", shadow: "#2f4a2c", sat: 0.9 },
  // ---------------------------------------------------------------- 2026 大厂产品配色
  { id: "10", group: "产品配色", name: "酒红", source: "iPhone 18 Pro 酒红 / 银色",
    note: "朱红收向酒红，银白高光，克制高级", light: "#f1e9e4", shadow: "#3a0d1a", sat: 0.92,
    families: { vermilion: "#8f1f2e" } },
  { id: "11", group: "产品配色", name: "宇宙橙 · 深蓝", source: "iPhone 17 Pro Cosmic Orange / Deep Blue",
    note: "电影感青橙对比", light: "#ff9b52", shadow: "#13284d", lightPull: 0.38, shadowPull: 0.5 },
  { id: "12", group: "产品配色", name: "钴紫 · 天蓝", source: "Galaxy S26 Ultra Cobalt Violet / Sky Blue",
    note: "冷调紫蓝，像月下宫城", light: "#d9e8ff", shadow: "#2c2266", families: { lapis: "#3c4fa8" } },
  { id: "13", group: "产品配色", name: "粉金", source: "Galaxy S26 Ultra Pink Gold",
    note: "柔粉金属光，暖灰阴影", light: "#ffd9c8", shadow: "#4a3038", sat: 0.85,
    families: { gold: "#dca86a" } },
  { id: "14", group: "产品配色", name: "峡谷 · 橄榄", source: "Pixel 11 Pro Canyon / Olive",
    note: "桃粉光照，橄榄阴影", light: "#ffc4a8", shadow: "#2e3420", families: { jade: "#5d6f3a" } },
  { id: "15", group: "产品配色", name: "雾 · 曜石", source: "Pixel 11 Pro Fog / Obsidian",
    note: "极简冷灰，低饱和高反差", light: "#e8eae8", shadow: "#16181d", sat: 0.62, lightPull: 0.4,
    shadowPull: 0.55 },
  { id: "16", group: "产品配色", name: "星空绿 · 冷烟紫", source: "小米 17 Ultra 星空绿 / 冷烟紫",
    note: "矿石绿高光，烟紫阴影", light: "#d4ecd9", shadow: "#3a3250", families: { jade: "#2e6b5a" } },
  { id: "17", group: "产品配色", name: "紫色日落", source: "华为 Pura 90 紫色日落 / 橙色海洋",
    note: "橙红晚霞，紫色暮影", light: "#ffae84", shadow: "#3b1f55", lightPull: 0.4, shadowPull: 0.48 },
  { id: "18", group: "产品配色", name: "翡翠 · 金", source: "华为 Pura 90 翡翠绿 / 金色",
    note: "金光翡翠影，富丽", light: "#ffd27a", shadow: "#0f3b2e", families: { jade: "#11795a", gold: "#e8b33a" } },
  // ---------------------------------------------------------------- 标准基准
  { id: "19", group: "标准基准", name: "D65 中性", source: "ITU-R BT.709 / CIE D65 白点",
    note: "不加情绪的中性参照，看原色", light: "#fffaf2", shadow: "#202224", lightPull: 0.08, shadowPull: 0.12 },
  { id: "20", group: "标准基准", name: "暮金宫阙", source: "现用情绪（OKLCH ≤20°）",
    note: "暖金主光，紫墨阴影", light: "#ffd8a0", shadow: "#2b2342" },
].map((p) => ({ ...base, ...p }));
