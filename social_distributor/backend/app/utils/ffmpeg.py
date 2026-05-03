"""ffmpeg wrappers for producing aspect-ratio derivatives.

We render three derivatives per source video:
- ``16:9`` for YouTube
- ``9:16`` for IG Reels / TikTok
- ``1:1``  for IG/FB grid posts

Cropping is centre-pad-and-scale: black bars are added if the source aspect
doesn't match, which is safer than cropping out content the creator may need.
"""
from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass

ASPECT_PRESETS: dict[str, tuple[int, int]] = {
    "16:9": (1920, 1080),
    "9:16": (1080, 1920),
    "1:1": (1080, 1080),
}


@dataclass
class TranscodeResult:
    aspect: str
    output_path: str


def ensure_ffmpeg() -> str:
    path = shutil.which("ffmpeg")
    if not path:
        raise RuntimeError("ffmpeg binary not found in PATH")
    return path


def transcode(input_path: str, output_path: str, aspect: str) -> TranscodeResult:
    width, height = ASPECT_PRESETS[aspect]
    ffmpeg = ensure_ffmpeg()
    # Scale to fit within the target box, then pad with black to the exact box.
    vf = (
        f"scale=w={width}:h={height}:force_original_aspect_ratio=decrease,"
        f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1"
    )
    cmd = [
        ffmpeg, "-y",
        "-i", input_path,
        "-vf", vf,
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "21",
        "-c:a", "aac", "-b:a", "128k",
        "-movflags", "+faststart",
        output_path,
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(
            f"ffmpeg failed for aspect {aspect}: {proc.stderr[-1000:]}"
        )
    return TranscodeResult(aspect=aspect, output_path=output_path)
