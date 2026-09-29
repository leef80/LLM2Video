"""Procedural score and ambience: guqin-like plucks, bronze bell, drum, wind, reverb."""
import numpy as np

SR = 48000


def resample(x, sr_in, sr_out=SR):
    if sr_in == sr_out:
        return x.astype(np.float32)
    n = int(len(x) * sr_out / sr_in)
    t = np.arange(n) * (sr_in / sr_out)
    return np.interp(t, np.arange(len(x)), x).astype(np.float32)


def pluck(freq, dur, bright=0.5, seed=0):
    """Karplus-Strong string, processed one period at a time (fast in numpy)."""
    rng = np.random.default_rng(seed)
    n = int(dur * SR)
    p = max(2, int(SR / freq))
    buf = rng.uniform(-1, 1, p)
    # soften the excitation for a warmer, guqin-like attack
    for _ in range(int(3 - 2 * bright)):
        buf = 0.5 * (buf + np.roll(buf, 1))
    # y[m] = decay * (y[m-p] + y[m-p-1]) / 2, computed one period at a time (only past samples are read)
    out = np.zeros(n + p + 1)
    out[1:p + 1] = buf
    decay = 0.996
    i = p + 1
    while i < n + p + 1:
        k = min(p, n + p + 1 - i)
        out[i:i + k] = decay * 0.5 * (out[i - p:i - p + k] + out[i - p - 1:i - p - 1 + k])
        i += k
    y = out[p + 1:]
    env = np.minimum(1, np.arange(n) / (0.004 * SR)) * np.exp(-np.arange(n) / (SR * dur * 0.35))
    body = y * env
    # a touch of the wooden body resonance
    t = np.arange(n) / SR
    body += 0.15 * np.sin(2 * np.pi * freq * t) * np.exp(-t * 2.5) * env
    return body.astype(np.float32)


def bell(freq=196.0, dur=6.0):
    t = np.arange(int(dur * SR)) / SR
    partials = [(0.5, 0.5, 1.2), (1.0, 1.0, 1.6), (1.19, 0.6, 2.2), (1.56, 0.45, 2.8), (2.0, 0.35, 3.2),
                (2.51, 0.25, 4.0), (3.01, 0.18, 5.0), (4.1, 0.1, 6.5)]
    y = np.zeros_like(t)
    for ratio, amp, dec in partials:
        y += amp * np.sin(2 * np.pi * freq * ratio * t + ratio) * np.exp(-t * dec / 1.6)
    y *= np.minimum(1, t / 0.003)
    y *= 1 + 0.08 * np.sin(2 * np.pi * 3.2 * t)  # slow beating
    return (y / np.abs(y).max()).astype(np.float32)


def drum(dur=1.6, seed=1):
    rng = np.random.default_rng(seed)
    t = np.arange(int(dur * SR)) / SR
    f = 55 + 45 * np.exp(-t * 18)
    ph = 2 * np.pi * np.cumsum(f) / SR
    y = np.sin(ph) * np.exp(-t * 3.2)
    y += 0.25 * rng.standard_normal(len(t)) * np.exp(-t * 40)
    return (y / np.abs(y).max()).astype(np.float32)


def wind(dur, seed=2):
    rng = np.random.default_rng(seed)
    n = int(dur * SR)
    w = np.cumsum(rng.standard_normal(n))
    w -= np.convolve(w, np.ones(4801) / 4801, mode="same")  # remove drift
    w /= np.abs(w).max() + 1e-9
    t = np.arange(n) / SR
    gust = 0.55 + 0.45 * np.sin(2 * np.pi * 0.07 * t + 1.0) * np.sin(2 * np.pi * 0.023 * t)
    return (w * gust).astype(np.float32)


def reverb_ir(dur=1.8, seed=3):
    rng = np.random.default_rng(seed)
    t = np.arange(int(dur * SR)) / SR
    ir = rng.standard_normal(len(t)) * np.exp(-t * 3.8)
    ir[: int(0.012 * SR)] = 0
    # darker tail
    k = np.ones(8) / 8
    ir = np.convolve(ir, k, mode="same")
    return (ir / np.sqrt((ir ** 2).sum())).astype(np.float32)


def convolve(x, ir):
    n = len(x) + len(ir) - 1
    nfft = 1 << (n - 1).bit_length()
    y = np.fft.irfft(np.fft.rfft(x, nfft) * np.fft.rfft(ir, nfft), nfft)[:len(x)]
    return y.astype(np.float32)


# D gong pentatonic, low register
SCALE = [146.83, 164.81, 185.00, 220.00, 246.94, 293.66, 329.63, 369.99, 440.00]
MOTIF = [(0, 5), (2.2, 4), (3.4, 3), (5.6, 5), (6.6, 7), (8.8, 5), (10.0, 4), (12.2, 3), (13.2, 1), (15.4, 0)]


def score(total, cues, duck):
    """Background music; `cues` = list of (time, kind) for bell/drum hits; `duck` in 0..1 per sample."""
    n = int(total * SR)
    mus = np.zeros(n, np.float32)
    t = np.arange(n) / SR
    # soft drone (D + A) with slow swell
    drone = (np.sin(2 * np.pi * 73.42 * t) + 0.5 * np.sin(2 * np.pi * 110.0 * t + 0.7)
             + 0.25 * np.sin(2 * np.pi * 146.83 * t + 1.3))
    drone *= 0.5 + 0.5 * np.sin(2 * np.pi * t / 17.0 - 1.2) ** 2
    mus += 0.035 * drone.astype(np.float32)
    # guqin phrases, repeating the motif with small variations
    rng = np.random.default_rng(4)
    start = 1.5
    loop = 18.0
    k = 0
    while start + k * loop < total - 2:
        for j, (dt, deg) in enumerate(MOTIF):
            at = start + k * loop + dt + rng.uniform(-0.05, 0.05)
            if at > total - 2.5:
                break
            d = deg if rng.random() > 0.25 else max(0, min(len(SCALE) - 1, deg + rng.choice([-1, 1])))
            note = pluck(SCALE[d], 3.2, bright=0.3, seed=k * 31 + j) * 0.22
            if j % 4 == 0:  # octave harmonic (泛音) sparkle
                harm = pluck(SCALE[d] * 2, 2.5, bright=0.6, seed=99 + j) * 0.06
                note[: len(harm)] += harm
            i = int(at * SR)
            e = min(n, i + len(note))
            mus[i:e] += note[: e - i]
        k += 1
    mus *= (1 - 0.55 * duck).astype(np.float32)
    for at, kind in cues:
        s = bell() * 0.5 if kind == "bell" else drum() * 0.55
        i = int(at * SR)
        e = min(n, i + len(s))
        if i < n:
            mus[i:e] += s[: e - i]
    mus += 0.025 * wind(total)
    return mus


def envelope(x, fps, total_frames):
    """Per-video-frame loudness (0..1) for lip-sync."""
    hop = SR / fps
    out = np.zeros(total_frames, np.float32)
    for f in range(total_frames):
        a = int(f * hop)
        seg = x[a: int(a + hop)]
        if len(seg):
            out[f] = np.sqrt((seg ** 2).mean())
    peak = np.percentile(out[out > 0], 95) if (out > 0).any() else 1.0
    out = np.clip(out / (peak + 1e-9), 0, 1)
    # light smoothing so the mouth doesn't flicker
    sm = np.convolve(out, [0.25, 0.5, 0.25], mode="same")
    return sm
