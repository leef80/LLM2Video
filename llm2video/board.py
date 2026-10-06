"""Render the mood palette (情绪色卡台) to a PNG:  python -m llm2video.board docs/palette.png"""
import sys

from PIL import Image, ImageDraw, ImageFont

from . import assets
from .palette import DATA, ROLES, _hex, luminance_ratio, pal, to_oklab

W = 1920
BG = (24, 21, 27)
FG = (238, 228, 210)
DIM = (150, 140, 128)

KEY_ROLES = [
    ("人物", ["skin", "skin.shade", "ink", "mouth", "minister.robe", "minister.hat", "badge.ground", "crane",
              "emperor.robe", "emperor.hat", "dragon", "guard.armor"]),
    ("建筑", ["hall.red", "hall.door", "hall.lattice", "roof.tile", "roof.tile.dark", "eave.under", "lintel.blue",
              "lintel.green", "plaque.ground", "plaque.text", "marble", "terrace"]),
    ("环境", ["steps", "pave", "pave.path", "bronze", "haze", "glow", "shadow", "cloud", "smoke", "leaf",
              "subtitle", "seal"]),
]


def _font(size):
    return ImageFont.truetype(assets.font("subtitle"), size)


def _ink_on(c):
    return (20, 16, 22) if to_oklab(tuple(c[:3]))[0] > 0.62 else (250, 244, 232)


def render(path):
    fams = DATA["families"]
    row_h, chip_w, left = 74, 130, 230
    h = 190 + len(fams) * (row_h + 18) + 140 + len(KEY_ROLES) * 108 + 90 + ((len(DATA["audit"]) + 2) // 3) * 70 + 60
    img = Image.new("RGB", (W, h), BG)
    d = ImageDraw.Draw(img)
    f_title, f_big, f, f_small = _font(64), _font(30), _font(22), _font(17)
    mood = DATA["mood"]
    d.text((60, 46), f"情绪色卡台 · {mood['name']}", font=f_title, fill=FG)
    d.text((64, 128), mood["note"] + "    同一明度阶梯 · 暗部偏紫墨 · 亮部偏暖金 · chroma.js / OKLCH", font=f, fill=DIM)
    for i, (k, lab) in enumerate((("light", "主光"), ("shadow", "阴影"))):
        x = W - 330 + i * 150
        d.rounded_rectangle([x, 50, x + 120, 110], 12, fill=_hex(mood[k]))
        d.text((x + 60, 80), lab, font=f, fill=_ink_on(_hex(mood[k])), anchor="mm")

    y = 190
    ladder = DATA["ladder"]
    for k, L in enumerate(ladder):
        d.text((left + k * chip_w + chip_w / 2 - 4, y - 14), f"{k}  L{L:.2f}", font=f_small, fill=DIM, anchor="mm")
    y += 8
    for name, fam in fams.items():
        d.text((60, y + 10), fam["label"], font=f_big, fill=FG)
        d.text((60, y + 48), f"{name} · {fam['note'].split('、')[0]}", font=f_small, fill=DIM)
        for k, hx in enumerate(fam["steps"]):
            c = _hex(hx)
            x = left + k * chip_w
            d.rectangle([x, y, x + chip_w - 8, y + row_h - 22], fill=c)
            if k == fam["baseStep"]:
                d.rectangle([x, y, x + chip_w - 8, y + row_h - 22], outline=FG, width=3)
            d.text((x + 8, y + row_h - 44), hx, font=f_small, fill=_ink_on(c))
        # continuous fine ramp under the steps
        fine = fam["fine"]
        x0, x1 = left, left + len(fam["steps"]) * chip_w - 8
        for i in range(x1 - x0):
            d.line([(x0 + i, y + row_h - 16), (x0 + i, y + row_h - 6)],
                   fill=_hex(fine[int(i / (x1 - x0) * (len(fine) - 1))]))
        y += row_h + 18

    # sky scale by elevation
    y += 20
    d.text((60, y + 8), "天空", font=f_big, fill=FG)
    d.text((60, y + 46), "按仰角取色", font=f_small, fill=DIM)
    stops = DATA["sky"]
    x0, x1 = left, left + len(ladder) * chip_w - 8
    lo, hi = stops[0][0], stops[-1][0]
    for i in range(x1 - x0):
        e = lo + (hi - lo) * i / (x1 - x0)
        for (ea, ca), (eb, cb) in zip(stops, stops[1:]):
            if ea <= e <= eb:
                t = (e - ea) / (eb - ea)
                c = tuple(int(a + (b - a) * t) for a, b in zip(_hex(ca), _hex(cb)))
                d.line([(x0 + i, y), (x0 + i, y + 60)], fill=c)
                break
    for e, _ in stops:
        x = x0 + (e - lo) / (hi - lo) * (x1 - x0)
        d.text((x, y + 76), f"{e}°", font=f_small, fill=DIM, anchor="mm")
    y += 120

    # key roles
    for group, roles in KEY_ROLES:
        d.text((60, y + 22), group, font=f_big, fill=FG)
        for i, r in enumerate(roles):
            c = pal(r)
            x = left + i * 140
            d.rounded_rectangle([x, y, x + 128, y + 64], 10, fill=tuple(c[:3]))
            d.text((x + 64, y + 78), r, font=f_small, fill=DIM, anchor="mm")
            tok = ROLES.get(r, "")
            d.text((x + 64, y + 32), tok.split(".", 1)[-1] if tok else "", font=f_small, fill=_ink_on(c), anchor="mm")
        y += 108

    # contrast audit
    y += 10
    d.text((60, y), "对比度自检（WCAG）", font=f_big, fill=FG)
    y += 56
    for i, a in enumerate(DATA["audit"]):
        col, row = i % 3, i // 3
        x, yy = 60 + col * 610, y + row * 70
        fg = pal(a["fg"]) if not a["fg"].startswith("#") else _hex(a["fg"])
        bg = pal(a["bg"]) if not a["bg"].startswith("#") else _hex(a["bg"])
        d.rounded_rectangle([x, yy, x + 96, yy + 54], 8, fill=tuple(bg[:3]))
        d.text((x + 48, yy + 27), "文Aa", font=f_big, fill=tuple(fg[:3]), anchor="mm")
        ratio = luminance_ratio(fg, bg)
        mark = "✓" if a["pass"] else "✗"
        d.text((x + 112, yy + 4), f"{mark} {a['why']}", font=f, fill=FG if a["pass"] else (255, 120, 100))
        note = f"{ratio:.2f} ≥ {a['min']}   APCA {a['apca']}"
        if a["moved"]:
            note += f"   自动 {a['moved']}"
        d.text((x + 112, yy + 32), note, font=f_small, fill=DIM)
    img.save(path, quality=90)
    return path


if __name__ == "__main__":
    print(render(sys.argv[1] if len(sys.argv) > 1 else "docs/palette.png"))
