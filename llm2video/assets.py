"""Locations of downloaded fonts and the offline TTS model (fetched by download_assets.py)."""
import os
import tarfile
import urllib.request
from pathlib import Path

ROOT = Path(os.environ.get("LLM2VIDEO_ASSETS", Path(__file__).resolve().parent.parent / "assets"))

FONTS = {
    # regular-script style font for subtitles and the palace plaque
    "subtitle": ("LXGWWenKai-Regular.ttf",
                 "https://github.com/lxgw/LxgwWenKai/releases/download/v1.330/LXGWWenKai-Regular.ttf"),
    "plaque": ("LXGWWenKai-Regular.ttf",
               "https://github.com/lxgw/LxgwWenKai/releases/download/v1.330/LXGWWenKai-Regular.ttf"),
    # brush calligraphy for the title card
    "title": ("MaShanZheng-Regular.ttf",
              "https://raw.githubusercontent.com/google/fonts/main/ofl/mashanzheng/MaShanZheng-Regular.ttf"),
}

TTS_MODEL = ("kokoro-multi-lang-v1_0",
             "https://github.com/k2-fsa/sherpa-onnx/releases/download/tts-models/kokoro-multi-lang-v1_0.tar.bz2")


def font(kind):
    return str(ROOT / "fonts" / FONTS[kind][0])


def tts_dir():
    return ROOT / "models" / TTS_MODEL[0]


def download(verbose=True):
    (ROOT / "fonts").mkdir(parents=True, exist_ok=True)
    (ROOT / "models").mkdir(parents=True, exist_ok=True)
    for name, url in {v[0]: v[1] for v in FONTS.values()}.items():
        dst = ROOT / "fonts" / name
        if not dst.exists():
            if verbose:
                print("downloading", url)
            urllib.request.urlretrieve(url, dst)
    if not (tts_dir() / "model.onnx").exists():
        arc = ROOT / "models" / (TTS_MODEL[0] + ".tar.bz2")
        if verbose:
            print("downloading", TTS_MODEL[1], "(~350 MB)")
        urllib.request.urlretrieve(TTS_MODEL[1], arc)
        with tarfile.open(arc) as t:
            t.extractall(ROOT / "models")
        arc.unlink()
