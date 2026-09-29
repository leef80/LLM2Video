"""Offline Mandarin speech with sherpa-onnx + Kokoro (no network needed once downloaded)."""
import re
from functools import lru_cache

import numpy as np

from . import assets

# sentence-level split keeps subtitles short and gives exact timings per chunk
_SPLIT = re.compile(r"(?<=[。！？!?；;])")
_COMMA = re.compile(r"(?<=[，,、：:])")


def split_line(text, max_len=16):
    """Split a line into subtitle-sized chunks, preferring sentence ends then commas."""
    chunks = []
    for sent in filter(None, (s.strip() for s in _SPLIT.split(text))):
        if len(sent) <= max_len:
            chunks.append(sent)
            continue
        cur = ""
        for part in filter(None, _COMMA.split(sent)):
            if cur and len(cur) + len(part) > max_len:
                chunks.append(cur)
                cur = part
            else:
                cur += part
        if cur:
            chunks.append(cur)
    return chunks


def speakable(text):
    """Text sent to the TTS engine: drop ellipses and quote marks that it would read oddly."""
    t = re.sub(r"[…\.]{2,}|…+", "", text)
    t = re.sub(r"[“”\"'《》]", "", t)
    return t.strip() or "嗯"


@lru_cache(maxsize=1)
def engine():
    import sherpa_onnx

    d = assets.tts_dir()
    cfg = sherpa_onnx.OfflineTtsConfig(
        model=sherpa_onnx.OfflineTtsModelConfig(
            kokoro=sherpa_onnx.OfflineTtsKokoroModelConfig(
                model=str(d / "model.onnx"), voices=str(d / "voices.bin"), tokens=str(d / "tokens.txt"),
                data_dir=str(d / "espeak-ng-data"), dict_dir=str(d / "dict"),
                lexicon=f"{d / 'lexicon-zh.txt'},{d / 'lexicon-us-en.txt'}"),
            num_threads=4),
        rule_fsts=f"{d / 'phone-zh.fst'},{d / 'date-zh.fst'},{d / 'number-zh.fst'}")
    return sherpa_onnx.OfflineTts(cfg)


def synth(text, voice, speed=1.0):
    """Return (float32 samples, sample_rate) with leading/trailing silence trimmed."""
    tts = engine()
    a = tts.generate(speakable(text), sid=int(voice), speed=float(speed))
    x = np.asarray(a.samples, dtype=np.float32)
    thr = 0.01 * (np.abs(x).max() + 1e-9)
    idx = np.where(np.abs(x) > thr)[0]
    if len(idx):
        pad = int(0.03 * a.sample_rate)
        x = x[max(0, idx[0] - pad): idx[-1] + pad]
    return x, a.sample_rate
