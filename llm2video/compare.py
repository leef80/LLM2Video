"""Comparison sheets for colour-space choices.

    python -m llm2video.compare mixes mixes.json docs/mix_modes.png
    python -m llm2video.compare ramps docs/space_ramps.png a.json b.json ...
"""
import json
import sys

from PIL import Image, ImageDraw, ImageFont

from . import assets

BG, FG, DIM = (24, 21, 27), (238, 228, 210), (150, 140, 128)
MODE_NOTE = {"rgb": "RGB 直线插值", "lab": "CIE Lab", "lch": "CIE LCH", "oklab": "OKLab", "oklch": "OKLCH"}
SPACE_NOTE = {"oklab": "OKLab 混色（现用）", "lab": "CIE Lab 混色", "oklch": "OKLCH 转色相", "lch": "CIE LCH 转色相",
              "oklch20": "OKLCH 转色相 ≤20°"}


def _font(n):
    return ImageFont.truetype(assets.font("subtitle"), n)


def _hex(s):
    s = s.lstrip("#")
    return tuple(int(s[i:i + 2], 16) for i in (0, 2, 4))


def mixes(src, dst):
    data = json.load(open(src))
    modes = list(data[0]["modes"])
    cw, ch, left = 118, 46, 300
    h = 120 + len(data) * (len(modes) * (ch + 6) + 70)
    img = Image.new("RGB", (left + 9 * cw + 230, h), BG)
    d = ImageDraw.Draw(img)
    d.text((40, 30), "混色方式对比（chroma.js scale().mode()）", font=_font(40), fill=FG)
    d.text((40, 82), "右侧数字：中点的 OKLCH 彩度。彩度越低，中间色越灰、越脏。", font=_font(20), fill=DIM)
    y = 130
    for pair in data:
        d.text((40, y), pair["name"], font=_font(28), fill=FG)
        y += 46
        for m in modes:
            d.text((60, y + 10), MODE_NOTE[m], font=_font(20), fill=DIM)
            for i, hx in enumerate(pair["modes"][m]["hex"]):
                d.rectangle([left + i * cw, y, left + (i + 1) * cw - 4, y + ch], fill=_hex(hx))
            mid = pair["modes"][m]["chroma"][4]
            d.text((left + 9 * cw + 20, y + 10), f"C {mid:.3f}", font=_font(20), fill=DIM)
            y += ch + 6
        y += 24
    img.save(dst)


def ramps(dst, paths, fams=("vermilion", "gold", "skin", "jade", "lapis", "stone", "ink")):
    pals = [json.load(open(p)) for p in paths]
    cw, ch, left = 96, 44, 260
    block = len(pals) * (ch + 6) + 56
    img = Image.new("RGB", (left + 11 * cw + 40, 120 + len(fams) * block), BG)
    d = ImageDraw.Draw(img)
    d.text((40, 30), "不同色彩空间生成的色阶", font=_font(40), fill=FG)
    d.text((40, 82), "同一套基色、同一情绪（暖金主光 / 紫墨阴影），只换生成色阶的空间与方法", font=_font(20), fill=DIM)
    y = 130
    for fam in fams:
        d.text((40, y), f"{pals[0]['families'][fam]['label']}  {fam}", font=_font(26), fill=FG)
        y += 44
        for p in pals:
            d.text((60, y + 10), SPACE_NOTE.get(p.get("space", "oklab"), p.get("space")), font=_font(19), fill=DIM)
            for i, hx in enumerate(p["families"][fam]["steps"]):
                d.rectangle([left + i * cw, y, left + (i + 1) * cw - 4, y + ch], fill=_hex(hx))
            y += ch + 6
        y += 12
    img.save(dst)


def stills(dst, rows, labels, frames):
    """rows: list of directories holding preview_XXXXX.png, one row per variant."""
    w, h = 640, 290
    img = Image.new("RGB", (220 + len(frames) * (w + 6), 60 + len(rows) * (h + 6)), BG)
    d = ImageDraw.Draw(img)
    for r, (row, lab) in enumerate(zip(rows, labels)):
        y = 60 + r * (h + 6)
        d.text((20, y + h / 2), lab, font=_font(24), fill=FG, anchor="lm")
        for c, f in enumerate(frames):
            im = Image.open(f"{row}/preview_{f:05d}.png").resize((w, 360)).crop((0, 35, w, 325))
            img.paste(im, (220 + c * (w + 6), y))
    d.text((20, 20), "同一镜头 · 不同色彩空间的色卡台", font=_font(28), fill=FG)
    img.save(dst, quality=88)


def _wrap(d, text, font, width):
    lines, cur = [], ""
    for ch in text:
        if d.textlength(cur + ch, font=font) > width:
            lines.append(cur)
            cur = ch
        else:
            cur += ch
    return lines + ([cur] if cur else [])


CARD_ROLES = ["minister.robe", "emperor.robe", "hall.red", "roof.tile", "lintel.blue", "lintel.green", "skin",
              "steps", "pave"]


def _role_hex(p, role):
    fam, step = p["roles"][role].split(".", 1)
    fine = p["families"][fam]["fine"]
    return fine[round(float(step) * (len(fine) - 1) / 10)]


def versions(dst_prefix, palettes, still_dirs, frames, per_sheet=5):
    """One card per palette version: name, source, mood + role swatches, then the stills."""
    w, h = 560, 254
    card_h = 70 + h + 20
    sheets = []
    for s0 in range(0, len(palettes), per_sheet):
        chunk = list(zip(palettes[s0:s0 + per_sheet], still_dirs[s0:s0 + per_sheet]))
        img = Image.new("RGB", (330 + len(frames) * (w + 6), 20 + len(chunk) * card_h), BG)
        d = ImageDraw.Draw(img)
        for r, (p, sd) in enumerate(chunk):
            y = 20 + r * card_h
            pr = p["preset"]
            d.text((24, y), f"{pr['id']}  {pr['name']}", font=_font(36), fill=FG)
            lines = _wrap(d, f"{pr['group']} · {pr['source']}", _font(17), 290)[:2]
            lines += _wrap(d, p["mood"]["note"], _font(17), 290)[:1]
            for k, ln in enumerate(lines):
                d.text((24, y + 46 + k * 20), ln, font=_font(17), fill=DIM)
            # mood light / shadow
            for k, key in enumerate(("light", "shadow")):
                d.rounded_rectangle([24 + k * 70, y + 112, 84 + k * 70, y + 154], 8, fill=_hex(p["mood"][key]))
            d.text((24, y + 158), "主光  阴影", font=_font(16), fill=DIM)
            for i, role in enumerate(CARD_ROLES):
                x = 24 + (i % 5) * 58
                yy = y + 190 + (i // 5) * 58
                d.rectangle([x, yy, x + 50, yy + 50], fill=_hex(_role_hex(p, role)))
            for c, f in enumerate(frames):
                im = Image.open(f"{sd}/preview_{f:05d}.png").resize((w, 315)).crop((0, 31, w, 31 + h))
                img.paste(im, (330 + c * (w + 6), y + 50))
        path = f"{dst_prefix}_{s0 // per_sheet + 1}.jpg"
        img.save(path, quality=86)
        sheets.append(path)
    return sheets


def overview(dst, palettes, still_dirs, frame, cols=4):
    w, h = 470, 213
    rows = (len(palettes) + cols - 1) // cols
    img = Image.new("RGB", (cols * (w + 8) + 8, 70 + rows * (h + 44)), BG)
    d = ImageDraw.Draw(img)
    d.text((14, 16), "二十版色卡台 · 总览", font=_font(32), fill=FG)
    for i, (p, sd) in enumerate(zip(palettes, still_dirs)):
        x, y = 8 + (i % cols) * (w + 8), 70 + (i // cols) * (h + 44)
        im = Image.open(f"{sd}/preview_{frame:05d}.png").resize((w, 264)).crop((0, 26, w, 26 + h))
        img.paste(im, (x, y))
        d.text((x, y + h + 6), f"{p['preset']['id']} {p['preset']['name']}", font=_font(22), fill=FG)
    img.save(dst, quality=86)


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "mixes":
        mixes(sys.argv[2], sys.argv[3])
    elif cmd == "ramps":
        ramps(sys.argv[2], sys.argv[3:])
