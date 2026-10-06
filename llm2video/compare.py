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


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "mixes":
        mixes(sys.argv[2], sys.argv[3])
    elif cmd == "ramps":
        ramps(sys.argv[2], sys.argv[3:])
