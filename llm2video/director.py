"""Turn a JSON screenplay into a finished MP4: TTS -> timeline -> animated frames -> ffmpeg."""
import json
import math
import subprocess
import wave
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from . import assets, audio, tts
from .figures import Pose, sprite
from .paint import soft_blob
from .palace import EMPEROR_POS, H, L, MINISTER_POS, paste_rgba, render_static

ANCHOR_H = 1.35      # height (m) at which character billboards are pinned to the 3D scene
MARGIN = 1.2          # static layers are rendered this much larger than the frame for camera moves
LETTERBOX = 2.2       # visible aspect ratio

# Camera presets: 3D placement + a slow 2D push (zoom from/to, drift in canvas fractions).
CAMERAS = {
    "wide": dict(pos=(0, 2.2, -30), target=(0, 7.5, 6), fov=40, zoom=(1.0, 1.12), drift=(0.0, 0.02)),
    "wide_end": dict(pos=(0, 2.4, -25), target=(0, 5.8, 4), fov=40, zoom=(1.16, 1.02), drift=(0.0, 0.0)),
    "low": dict(pos=(0.62, 1.15, -4.65), target=(0, H + 0.4, L + 0.6), fov=42, zoom=(1.0, 1.07), drift=(0.0, -0.01)),
    "high": dict(pos=(-1.1, H + 2.9, L + 2.2), target=(0, 1.2, -0.8), fov=40, zoom=(1.0, 1.07), drift=(0.0, 0.01)),
    "emperor_close": dict(pos=(0.3, H + 0.85, L - 1.5), target=(0.1, H + 1.85, L + 0.6), fov=38, zoom=(1.0, 1.1),
                          drift=(0.0, 0.0)),
    "minister_close": dict(pos=(0.45, 2.0, -1.0), target=(0.25, 1.5, -3.0), fov=36, zoom=(1.0, 1.1),
                           drift=(0.0, 0.0)),
}

# which characters appear in each preset, with the view they present to that camera
CAST = {
    "wide": [("minister", "back"), ("emperor", "front")],
    "wide_end": [("minister", "back"), ("emperor", "front")],
    "low": [("minister", "back"), ("emperor", "front")],
    "high": [("emperor", "back"), ("minister", "front")],
    "emperor_close": [("emperor", "front")],
    "minister_close": [("minister", "front")],
}
POS = {"minister": MINISTER_POS, "emperor": EMPEROR_POS}


def smooth(x, a, b):
    if b <= a:
        return 1.0 if x >= b else 0.0
    t = min(1.0, max(0.0, (x - a) / (b - a)))
    return t * t * (3 - 2 * t)


@dataclass
class Sub:
    start: float
    end: float
    text: str
    speaker: str


@dataclass
class Shot:
    spec: dict
    start: float = 0.0
    duration: float = 0.0
    speech: list = field(default_factory=list)   # (t_start_local, samples) at audio.SR

    @property
    def camera(self):
        return self.spec["camera"]

    @property
    def speech_end(self):
        if not self.speech:
            return self.spec.get("pre", 0.45)
        t, x = self.speech[-1]
        return t + len(x) / audio.SR


# ----------------------------------------------------------------------------- timeline

def build_timeline(play, log=print):
    chars = play["characters"]
    shots, subs = [], []
    t = 0.0
    for spec in play["shots"]:
        sh = Shot(spec)
        sh.start = t
        pre = spec.get("pre", 0.45)
        local = pre
        if spec.get("line"):
            who = spec["speaker"]
            voice = chars[who]
            chunks = tts.split_line(spec["line"])
            for i, ch in enumerate(chunks):
                x, sr = tts.synth(ch, voice["voice"], voice.get("speed", 1.0))
                x = audio.resample(x, sr)
                sh.speech.append((local, x))
                dur = len(x) / audio.SR
                subs.append(Sub(t + local - 0.05, t + local + dur + 0.15, ch, who))
                local += dur
                if i < len(chunks) - 1:
                    local += 0.3 if ch[-1] in "，,、：:" else 0.5
            log(f"  {chars[who]['name']}: {spec['line']}  ({local - pre:.1f}s)")
        sh.duration = spec.get("duration", local + spec.get("tail", 0.75))
        t += sh.duration
        shots.append(sh)
    # merge subtitle end times so consecutive chunks don't flicker
    for a, b in zip(subs, subs[1:]):
        if b.start - a.end < 0.35:
            a.end = b.start
    return shots, subs, t


def build_audio(shots, total, fps, n_frames):
    n = int(total * audio.SR) + audio.SR
    voice = {"emperor": np.zeros(n, np.float32), "minister": np.zeros(n, np.float32)}
    cues = []
    for sh in shots:
        who = sh.spec.get("speaker")
        for t, x in sh.speech:
            i = int((sh.start + t) * audio.SR)
            voice[who][i:i + len(x)] += x
        if sh.spec.get("cue"):
            at = sh.start + (0.25 if sh.spec["cue"] == "bell" else max(0.05, sh.spec.get("pre", 0.45) - 0.6))
            cues.append((at, sh.spec["cue"]))
    dry = voice["emperor"] + voice["minister"]
    env_all = np.abs(dry)
    duck = np.convolve(env_all > 0.02, np.ones(int(0.25 * audio.SR)) / int(0.25 * audio.SR), mode="same")
    duck = np.clip(duck * 3, 0, 1)
    music = audio.score(n / audio.SR, cues, duck)
    wet = audio.convolve(dry, audio.reverb_ir())
    mix = dry * 0.9 + wet * 0.22 + music[:n]
    # fade in/out
    fade = int(1.5 * audio.SR)
    mix[:int(0.3 * audio.SR)] *= np.linspace(0, 1, int(0.3 * audio.SR))
    end = int(total * audio.SR)
    mix[end - fade:end] *= np.linspace(1, 0, fade)
    mix[end:] = 0
    mix = mix[:end]
    mix /= max(1e-6, np.abs(mix).max()) / 0.89
    envs = {k: audio.envelope(v, fps, n_frames) for k, v in voice.items()}
    return mix, envs


def write_wav(path, x, sr):
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes((np.clip(x, -1, 1) * 32767).astype("<i2").tobytes())


# ----------------------------------------------------------------------------- per-shot visuals

class ShotRender:
    def __init__(self, name, size):
        self.name = name
        p = dict(CAMERAS[name])
        self.p = p
        w, h = size
        self.cw, self.ch = int(w * MARGIN), int(h * MARGIN)
        sky, world, cam, horizon = render_static(p, (self.cw, self.ch))
        self.sky = sky.convert("RGBA")
        self.world = world
        self.cam = cam
        self.horizon = horizon
        rng = np.random.default_rng(hash(name) % 1000)
        self.clouds = []
        for _ in range(7):
            y = rng.uniform(-0.1, 0.55) * max(0.0, min(self.ch, horizon))
            self.clouds.append((rng.uniform(-0.2, 1.1) * self.cw, y, rng.uniform(120, 320) * MARGIN,
                                rng.uniform(25, 60) * MARGIN, rng.uniform(4, 10)))
        self.cloud_img = {}
        for i, (_, _, rx, ry, _) in enumerate(self.clouds):
            base = Image.new("RGBA", (int(rx * 2.6), int(ry * 4)), (0, 0, 0, 0))
            for k in range(5):
                b = soft_blob(rx * rng.uniform(0.35, 0.6), ry * rng.uniform(0.6, 1.0), (255, 246, 232, 150),
                              ry * 0.5)
                base.alpha_composite(b, (int(rng.uniform(0, base.width - b.width)) if base.width > b.width else 0,
                                         int(rng.uniform(0, max(1, base.height - b.height)))))
            self.cloud_img[i] = base

    def smoke_sources(self):
        out = []
        for x in (-5.5, 5.5):
            p = (x, H + 1.7, L + 5.5)
            if self.cam.depth(p) > 1:
                sx, sy = self.cam.project([p])[0]
                out.append((sx, sy, self.cam.scale_at(p)))
        return out


@lru_cache(maxsize=64)
def _puff(radius, alpha):
    return soft_blob(radius, radius, (236, 232, 226, alpha), radius * 0.6)


@lru_cache(maxsize=512)
def _blurred(who, view, key, scale, blur):
    pose = Pose(key[0] / 5, key[1], key[2] / 12, key[3] / 16, key[4] / 16, key[5] / 12, (key[6] / 4, key[7] / 4))
    return sprite(who, view, pose, scale, blur=blur)


def _leaf_sprite(size, angle, squash):
    s = size * 3
    im = Image.new("RGBA", (s * 2, s * 2), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    fan = [(s, s * 1.5)]
    for k in range(9):
        a = math.radians(200 + k * 17.5)
        fan.append((s + math.cos(a) * s * 0.9, s + math.sin(a) * s * 0.9 * 0.85))
    d.polygon(fan, fill=(236, 186, 52, 235))
    d.line([(s, s * 1.5), (s, s * 1.9)], fill=(170, 120, 30, 235), width=max(1, s // 10))
    im = im.resize((max(1, int(im.width * max(0.15, abs(squash)))), im.height), Image.BICUBIC)
    return im.rotate(angle, resample=Image.BICUBIC, expand=True).resize(
        (max(1, im.width // 3 + 1), max(1, im.height // 3 + 1)), Image.LANCZOS)


class Post:
    """Colour grade, light rays, vignette, grain, letterbox."""

    def __init__(self, size):
        w, h = size
        self.w, self.h = w, h
        yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
        r = np.sqrt(((xx - w / 2) / (w / 2)) ** 2 + ((yy - h / 2) / (h / 2)) ** 2)
        self.vig = (1 - 0.32 * np.clip(r - 0.35, 0, 1) ** 1.6)[..., None].astype(np.float32)
        rays = Image.new("L", (w, h), 0)
        d = ImageDraw.Draw(rays)
        rng = np.random.default_rng(8)
        for _ in range(7):
            a = rng.uniform(0.35, 0.8)
            wdt = rng.uniform(0.02, 0.07)
            ox = -0.15 * w
            oy = -0.25 * h
            ln = 2.2 * w
            p1 = (ox + math.cos(a - wdt) * ln, oy + math.sin(a - wdt) * ln)
            p2 = (ox + math.cos(a + wdt) * ln, oy + math.sin(a + wdt) * ln)
            d.polygon([(ox, oy), p1, p2], fill=int(rng.uniform(40, 90)))
        rays = rays.filter(ImageFilter.GaussianBlur(28))
        fall = np.clip(1.2 - np.sqrt((xx / w) ** 2 + (yy / h) ** 2), 0, 1)
        self.rays = (np.asarray(rays, np.float32) / 255 * fall)[..., None] * np.array([255, 222, 170], np.float32)
        self.grain = [np.random.default_rng(i).normal(0, 1.4, (h, w, 1)).astype(np.float32) for i in range(6)]
        self.bar = int(round((h - w / LETTERBOX) / 2))

    def apply(self, img, frame, ray_amt=0.12, fade=1.0):
        a = np.asarray(img, np.float32)[..., :3]
        a = a + self.rays * ray_amt * (1 - a / 255)          # screen-ish blend
        a = a * np.array([1.03, 1.0, 0.94], np.float32)       # warm grade
        a = 255 * (a / 255) ** 1.04
        a = (a - 128) * 1.06 + 128
        a *= self.vig
        a += self.grain[frame % len(self.grain)]
        a *= fade
        a[: self.bar] = 0
        a[self.h - self.bar:] = 0
        return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8), "RGB")


# ----------------------------------------------------------------------------- main render

class Director:
    def __init__(self, play, log=print):
        self.play = play
        self.fps = play.get("fps", 24)
        self.size = tuple(play.get("size", (1920, 1080)))
        self.log = log

    def pose_for(self, who, sh, tl, frame, envs):
        spec = sh.spec
        speaking = spec.get("speaker") == who
        mouth = float(envs[who][frame]) if speaking and frame < len(envs[who]) else 0.0
        offs = 0.0 if who == "emperor" else 1.7
        blink = ((tl + sh.start + offs) % 3.9) < 0.13
        p = Pose(mouth=mouth, blink=blink)
        pre = spec.get("pre", 0.45)
        if who == "minister":
            p.look = (0.0, 1.0)
            p.bow = 0.12 + 0.1 * mouth
            if spec.get("action") == "bow":
                p.bow = 0.75 - 0.5 * smooth(tl, pre + 0.3, pre + 1.8) + 0.1 * mouth
            if spec.get("action") == "kowtow":
                p.kneel = smooth(tl, 0.15, 1.0)
                p.prostrate = smooth(tl, sh.speech_end + 0.1, sh.speech_end + 1.0)
        else:
            p.look = (0.0, -1.0)
            if spec.get("action") == "gesture":
                p.gesture = smooth(tl, pre + 1.3, pre + 1.9) * (1 - smooth(tl, sh.duration - 1.2, sh.duration - 0.4))
        return p

    def frame(self, sr, sh, tl, frame, envs):
        cam = sr.cam
        canvas = sr.sky.copy()
        # clouds and birds live behind the world layer
        for i, (x, y, rx, ry, v) in enumerate(sr.clouds):
            ci = sr.cloud_img[i]
            xx = (x + v * MARGIN * (sh.start + tl)) % (sr.cw + ci.width) - ci.width
            paste_rgba(canvas, ci, xx, y - ci.height / 2)
        if sr.name == "wide":
            d = ImageDraw.Draw(canvas)
            for b in range(7):
                bx = sr.cw * (1.05 - 0.09 * tl) + b * 38 * MARGIN + 20 * math.sin(b * 1.7)
                by = sr.ch * 0.16 + b * 11 * MARGIN * (1 if b % 2 else -0.6) + 6 * math.sin(tl * 1.3 + b)
                flap = math.sin(tl * 9 + b * 1.1) * 7 * MARGIN
                d.line([(bx - 10 * MARGIN, by - flap), (bx, by), (bx + 10 * MARGIN, by - flap)], fill=(40, 34, 30),
                       width=max(2, int(2.2 * MARGIN)))
        canvas.alpha_composite(sr.world)
        # incense smoke from the bronze tripods
        for sx, sy, sc in sr.smoke_sources():
            t = sh.start + tl
            for k in range(14):
                life = 5.0
                age = (t + k * life / 14) % life
                f = age / life
                px = sx + (math.sin(age * 1.3 + k) * 0.18 + f * 0.6) * sc
                py = sy - f * 2.6 * sc
                rad = max(2, int((0.12 + f * 0.45) * sc))
                a = int(110 * (1 - f) * min(1, age * 3))
                if a > 4:
                    pf = _puff(rad, max(8, a // 8 * 8))
                    paste_rgba(canvas, pf, px - pf.width / 2, py - pf.height / 2)
        # characters, far to near
        people = []
        for who, view in CAST[sr.name]:
            pos = np.array(POS[who], dtype=float)
            depth = cam.depth(pos + [0, 1.0, 0])
            people.append((depth, who, view, pos))
        for depth, who, view, pos in sorted(people, key=lambda t: -t[0]):
            pose = self.pose_for(who, sh, tl, frame, envs)
            # anchor at shoulder height: for near cameras the feet project with a very different scale
            anchor = pos + [0, ANCHOR_H, 0]
            scale = round(cam.scale_at(anchor), 1)
            blur = 0.0
            if depth < 4.0 and sr.name in ("low", "high"):
                blur = 5.0 * MARGIN
                if view == "back":
                    pose.mouth, pose.blink = 0.0, False
            spr, (ax, ay) = _blurred(who, view, pose.key(), scale, blur)
            fx, fy = cam.project([anchor])[0]
            fy += ANCHOR_H * scale
            breathe = math.sin((sh.start + tl) * 2 * math.pi / 3.6 + (0 if who == "emperor" else 1)) * 0.004 * scale
            if not (who == "minister" and pose.kneel > 0):
                sh_img = _shadow(int(0.4 * scale), int(0.09 * scale) + 1)
                if depth > 4.0:
                    paste_rgba(canvas, sh_img, fx - sh_img.width / 2, fy - sh_img.height / 2)
            paste_rgba(canvas, spr, fx - ax, fy - ay + breathe)
        # 2D camera move
        p = sr.p
        k = smooth(tl, 0, sh.duration) if sh.duration > 0 else 0
        z = p["zoom"][0] + (p["zoom"][1] - p["zoom"][0]) * k
        cw, ch = sr.cw / z, sr.ch / z
        cx = sr.cw / 2 + p["drift"][0] * sr.cw * k
        cy = sr.ch / 2 + p["drift"][1] * sr.ch * k
        cx = min(max(cx, cw / 2), sr.cw - cw / 2)
        cy = min(max(cy, ch / 2), sr.ch - ch / 2)
        box = (cx - cw / 2, cy - ch / 2, cx + cw / 2, cy + ch / 2)
        out = canvas.resize(self.size, Image.BILINEAR, box=box, reducing_gap=None)
        # falling ginkgo leaves and floating motes in screen space
        t = sh.start + tl
        for i in range(4):
            period = 9.0 + i * 1.7
            ph = (t / period + i * 0.37) % 1.0
            lx = self.size[0] * (0.15 + 0.25 * i + 0.25 * ph) + 60 * math.sin(t * 0.9 + i)
            ly = -40 + ph * (self.size[1] + 80)
            ang = (t * 70 + i * 50) % 360
            leaf = _leaf_cached(int(ang // 15 * 15), round(math.cos(t * 2.2 + i), 1))
            paste_rgba(out, leaf, lx, ly)
        return out

    def render(self, out_path, workdir, preview_frames=None):
        workdir = Path(workdir)
        workdir.mkdir(parents=True, exist_ok=True)
        self.log("synthesising dialogue ...")
        shots, subs, total = build_timeline(self.play, self.log)
        n_frames = int(math.ceil(total * self.fps))
        self.log(f"total {total:.1f}s, {n_frames} frames")
        mix, envs = build_audio(shots, total, self.fps, n_frames)
        wav = workdir / "audio.wav"
        write_wav(wav, mix, audio.SR)
        post = Post(self.size)
        overlay = Overlays(self.play, self.size, post.bar)
        renders = {}
        ff = None
        if preview_frames is None:
            ff = subprocess.Popen(
                [ffmpeg_exe(), "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
                 "-s", f"{self.size[0]}x{self.size[1]}", "-r", str(self.fps), "-i", "-", "-i", str(wav),
                 "-c:v", "libx264", "-preset", "slow", "-tune", "animation", "-crf", "20", "-pix_fmt", "yuv420p",
                 "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", str(out_path)],
                stdin=subprocess.PIPE)
        si = 0
        frames = range(n_frames) if preview_frames is None else preview_frames
        for f in frames:
            t = f / self.fps
            while si < len(shots) - 1 and t >= shots[si + 1].start:
                si += 1
            sh = shots[si]
            name = sh.camera
            if name not in renders:
                self.log(f"  rendering set for shot '{name}' ...")
                renders[name] = ShotRender(name, self.size)
            img = self.frame(renders[name], sh, t - sh.start, f, envs)
            fade = min(1.0, t / 1.2, (total - t) / 1.8)
            img = post.apply(img, f, ray_amt=0.14 if name in ("low", "wide", "emperor_close") else 0.08,
                             fade=max(0.0, fade))
            overlay.draw(img, t, subs, shots[0].duration)
            if ff:
                ff.stdin.write(img.tobytes())
            else:
                img.save(workdir / f"preview_{f:05d}.png")
            if f % (self.fps * 5) == 0:
                self.log(f"  frame {f}/{n_frames}")
        if ff:
            ff.stdin.close()
            ff.wait()
            if ff.returncode:
                raise RuntimeError("ffmpeg failed")
        return total


@lru_cache(maxsize=32)
def _shadow(rx, ry):
    return soft_blob(rx, ry, (25, 18, 12, 90), max(2, ry * 0.6))


@lru_cache(maxsize=512)
def _leaf_cached(angle, squash):
    return _leaf_sprite(9, angle, squash)


class Overlays:
    """Title card and subtitles (drawn after grading so they stay crisp)."""

    def __init__(self, play, size, bar):
        self.play = play
        self.size = size
        self.bar = bar
        self.sub_font = ImageFont.truetype(assets.font("subtitle"), 46)
        self.title_font = ImageFont.truetype(assets.font("title"), 168)
        self.small_font = ImageFont.truetype(assets.font("subtitle"), 40)
        self.seal_font = ImageFont.truetype(assets.font("subtitle"), 38)
        self._title = self._make_title()

    def _make_title(self):
        w, h = self.size
        im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        title = self.play.get("title", "")
        cx, cy = w / 2, h * 0.36
        glow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        ImageDraw.Draw(glow).text((cx, cy), title, font=self.title_font, fill=(40, 20, 10, 200), anchor="mm")
        im.alpha_composite(glow.filter(ImageFilter.GaussianBlur(10)))
        d.text((cx, cy), title, font=self.title_font, fill=(252, 240, 214, 255), anchor="mm")
        bbox = d.textbbox((cx, cy), title, font=self.title_font, anchor="mm")
        # red seal
        sx, sy = bbox[2] + 26, bbox[1] + 10
        d.rectangle([sx, sy, sx + 64, sy + 88], fill=(178, 34, 28, 235))
        d.text((sx + 32, sy + 24), "问", font=self.seal_font, fill=(250, 236, 220, 255), anchor="mm")
        d.text((sx + 32, sy + 64), "对", font=self.seal_font, fill=(250, 236, 220, 255), anchor="mm")
        sub = self.play.get("subtitle", "")
        if sub:
            d.text((cx, bbox[3] + 50), sub, font=self.small_font, fill=(250, 236, 214, 235), anchor="mm")
        return im

    def draw(self, img, t, subs, title_dur):
        if t < title_dur:
            a = smooth(t, 0.9, 2.2) * (1 - smooth(t, title_dur - 2.0, title_dur - 0.6))
            if a > 0.01:
                arr = np.asarray(self._title).copy()
                arr[..., 3] = (arr[..., 3] * a).astype(np.uint8)
                img.paste(Image.fromarray(arr), (0, 0), Image.fromarray(arr))
        d = ImageDraw.Draw(img)
        for s in subs:
            if s.start <= t < s.end:
                a = min(1.0, (t - s.start) / 0.15, (s.end - t) / 0.15)
                c = int(248 * a)
                y = self.size[1] - self.bar / 2
                d.text((self.size[0] / 2, y), s.text, font=self.sub_font, fill=(c, int(c * 0.95), int(c * 0.86)),
                       anchor="mm", stroke_width=2, stroke_fill=(0, 0, 0))


def ffmpeg_exe():
    import shutil
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))
