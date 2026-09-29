#!/usr/bin/env python3
"""Render a screenplay JSON into an MP4.

    python make_video.py screenplays/danchi_wendui.json -o output/danchi_wendui.mp4
    python make_video.py screenplays/danchi_wendui.json --preview 30,200,600   # a few PNG stills
"""
import argparse
import functools
import time
from pathlib import Path

from llm2video import assets
from llm2video.director import Director, load


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("screenplay")
    ap.add_argument("-o", "--output", default=None)
    ap.add_argument("--work", default="build", help="directory for intermediate files")
    ap.add_argument("--preview", default=None, help="comma-separated frame numbers to save as PNG instead")
    args = ap.parse_args()

    assets.download()
    play = load(args.screenplay)
    out = Path(args.output or Path("output") / (Path(args.screenplay).stem + ".mp4"))
    out.parent.mkdir(parents=True, exist_ok=True)
    frames = [int(f) for f in args.preview.split(",")] if args.preview else None
    t0 = time.time()
    total = Director(play, log=functools.partial(print, flush=True)).render(out, args.work, preview_frames=frames)
    what = f"previews in {args.work}/" if frames else str(out)
    print(f"done: {what}  ({total:.1f}s of video, rendered in {time.time() - t0:.0f}s)")


if __name__ == "__main__":
    main()
