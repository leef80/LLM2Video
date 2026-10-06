# 配色调研：国际规范 · 流行色 · 2026 产品配色

调研日期 2026-10，用于生成 `grade/presets.mjs` 里的 20 版情绪色卡台。

## 一、国际规范：我们实际怎么用

| 机构 / 规范 | 内容 | 在本项目中的落地 |
| --- | --- | --- |
| **CIE 15:2018**、**ISO/CIE 11664-6（CIEDE2000）** | 色度学基础、CIELAB、ΔE₀₀ 色差公式 | 每个色族相邻两级的 ΔE₀₀ 必须 ≥ 5，保证色阶每一级都看得出区别；20 版全部通过 |
| **ITU-R BT.709-6** | 高清视频的三原色、D65 白点、传递函数和 YCbCr 矩阵 | 修正了编码：之前 ffmpeg 默认用 BT.601 矩阵把 RGB 转 YUV，高清播放器按 709 解码，朱红被看成偏红约 13 级、青绿偏暗约 10 级。现在按 709 矩阵转换并写入色彩标记 |
| **EBU R103** | 广播信号电平容差（8 bit 亮度 16–235 合法范围） | 输出改为 TV（limited）范围，并在码流里标注 |
| **W3C CSS Color 4** | OKLab / OKLCH 的标准定义 | 色阶、明度阶梯、转色相都在 OKLCH 里计算（chroma.js 实现） |
| **W3C WCAG 2.2**（1.4.3 / 1.4.11）、**APCA**（WCAG 3 草案） | 文字 4.5:1、非文字图形 3:1 的对比度要求 | 21 组必须分清的颜色自动检查，不达标时沿色阶挪位；同时给出 APCA 值作参考 |

## 二、国际流行色机构

| 来源 | 颜色 | 说明 |
| --- | --- | --- |
| Pantone 2026 年度色 | **Cloud Dancer**（PANTONE 11-4201，约 #F0EEE9） | 首个白色系年度色，“平静、重新开始” |
| WGSN × Coloro 2026 年度色 | **Transformative Teal**（介于蓝绿之间） | 关注地球、韧性 |
| WGSN × Coloro AW26/27 关键色 | Transformative Teal、Wax Paper、Fresh Purple、Cocoa Powder、Green Glow | 主题“Redirection”，强调两极对比 |
| WGSN × Coloro 2027 年度色 | **Luminous Blue**（Coloro 125-28-38） | 中性、跨季、神秘 |
| WGSN × Coloro SS27 关键色 | Luminous Blue、Energy Orange、Pop Pink（151-73-22）、Meadowland Green（050-61-19）、Clay（014-60-13） | |
| WGSN × Coloro AW27/28 关键色 | Russet、Peaceful Lilac、Maize、Deep Green | |

中国流行色协会 2026 年度色本次没有检索到可靠的公开资料，未纳入。

## 三、2026 大厂产品配色

| 产品 | 发布 | 配色 |
| --- | --- | --- |
| iPhone 18 Pro / Pro Max | 2026-09 | 浅蓝、银色、黑色、**酒红**（首次） |
| iPhone 17 Pro | 2025-09（在售） | Cosmic Orange、Deep Blue、Silver |
| Galaxy S26 Ultra | 2026-02 | White、Sky Blue、**Cobalt Violet**、Black；网店限定 Silver、**Pink Gold** |
| Pixel 11 Pro / Pro XL | 2026-08 | Obsidian、Fog、Olive、**Canyon**（桃粉） |
| 小米 17 Ultra | 2025-12 | 黑、白、**星空绿**（矿石颗粒质感）、**冷烟紫** |
| 华为 Pura 90 系列 | 2026 | Pro Max：黑、金、**紫色日落**、橙色海洋、**翡翠绿**；Pro：桑葚黑、椰子白、橙色苏打、粉红番石榴 |

趋势小结：
- **深沉的红**回归旗舰：iPhone 酒红。
- **紫色**全面上位：钴紫、冷烟紫、紫色日落、Fresh Purple、丁香。
- **自然绿**持续：橄榄、星空绿、翡翠绿、深绿。
- **暖粉和桃色**取代冷粉：Canyon、粉金、Pop Pink。
- **极浅的暖白**：Cloud Dancer。

## 注意

- 流行色的色值是根据公开名称和 Coloro 编码估算的近似值，不是官方色样数据。
- 产品配色来自新闻和零售商报道，个别中文译名可能与官方命名不同。
- 部分来源（如 WGSN 官网）无法直接访问，信息经由新闻报道转引。

## 来源

- Pantone 2026：[NBC News](https://www.nbcnews.com/pop-culture/pop-culture-news/pantone-names-2026-color-year-rcna247366)；色值：[hextoral](https://hextoral.com/hex-color/F0EEE9/pantone-fashion-home-interiors/)
- WGSN × Coloro：[2026 Transformative Teal（MR Magazine）](https://mr-mag.com/wgsn-and-coloro-announce-colour-of-the-year-2026-transformative-teal-and-the-key-colours-for-a-w-26-27)、[2027 Luminous Blue（FashionUnited）](https://fashionunited.com/news/fashion/wgsn-and-coloro-name-luminous-blue-colour-of-the-year-2027/2025042965718)、[SS27 关键色](https://fashionunited.uk/news/fashion/spotted-on-the-catwalk-the-wgsn-spring-summer-2027-colours/2025101484366)、[AW27/28 关键色](https://fashionunited.uk/news/fashion/wgsn-and-coloro-key-colours-for-autumn-winter-2027-28/2025091783967)
- iPhone 18 Pro：[Coolblue](https://www.coolblue.de/en/advice/what-are-the-iphone-18-series-colors.html)
- Galaxy S26 Ultra：[PhoneArena](https://www.phonearena.com/news/samsung-galaxy-s26-ultra-only-two-online-exclusive-color-options_id178394)、[9to5Google](https://9to5google.com/2026/02/03/samsung-galaxy-s26-ultra-render-leaks-showcase-all-four-familiar-colors/)
- Pixel 11：[Tech Advisor](https://www.techadvisor.com/article/3190429/pixel-11-official-colours-ranked-insipid-to-miami-sunset.html)、[T3](https://www.t3.com/tech/phones/heres-every-pixel-11-in-every-colour-as-google-reveals-2026-flagships)
- 小米 17 Ultra：[IT之家](https://www.ithome.com/0/908/012.htm)、[Notebookcheck](https://www.notebookcheck.net/Official-Multiple-launch-colours-confirmed-for-Xiaomi-17-Ultra-and-Xiaomi-17-globally.1233019.0.html)
- 华为 Pura 90：[Smartprix](https://us.smartprix.com/mobiles/huawei_pura_90_pro_max_vs_xiaomi_17_ultra-cpd179a0quhv_pd136rcvxif.php)、[Huawei Central](https://www.huaweicentral.com/huawei-pura-90-series-rumored-to-feature-nine-new-colors/amp/)
- 规范：[ITU-R BT.709](https://www.itu.int/rec/R-REC-BT.709)、[EBU R103](https://tech.ebu.ch/publications/r103)、[CIE 15:2018](https://cie.co.at/publications/colorimetry-4th-edition)、[CSS Color 4](https://www.w3.org/TR/css-color-4/)、[WCAG 2.2](https://www.w3.org/TR/WCAG22/)
