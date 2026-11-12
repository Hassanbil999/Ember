"""Frame access. Image sequences are read file-by-file; videos are split to PNG with ffmpeg
(the imageio-ffmpeg bundled binary, or system ffmpeg) — whole videos are never loaded."""
from __future__ import annotations

import glob
import shutil
import subprocess
from pathlib import Path

import cv2
import numpy as np

from ..core.config import ARTIFACTS, RAW

FRAME_CACHE = ARTIFACTS / "frames"
IMG_EXT = (".png", ".tif", ".tiff", ".bmp", ".jpg", ".jpeg")
VIDEO_EXT = (".avi", ".mp4", ".mov", ".mkv")


def ffmpeg_exe() -> str:
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def extract_video(path: Path, out_dir: Path, scale_height: int | None = None) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    existing = sorted(out_dir.glob("f*.png"))
    if existing:
        return existing
    vf = ["-vf", f"scale=-2:{scale_height}"] if scale_height else []
    cmd = [ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-i", str(path), *vf, "-start_number", "0",
           str(out_dir / "f%04d.png")]
    subprocess.run(cmd, check=True)
    return sorted(out_dir.glob("f*.png"))


def frame_paths(media: dict) -> list[Path]:
    p = RAW / media["path"]
    if p.is_dir():
        files = []
        for ext in IMG_EXT:
            files += glob.glob(str(p / f"*{ext}"))
        return [Path(f) for f in sorted(files)]
    if p.suffix.lower() in VIDEO_EXT:
        return extract_video(p, FRAME_CACHE / media["id"])
    return [p]


def read_frame(path: Path, color: bool = False) -> np.ndarray:
    img = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
    if img is None:
        raise FileNotFoundError(path)
    if img.dtype != np.uint8:   # 12/16-bit TIFFs from science cameras
        img = cv2.normalize(img, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
    if color:
        if img.ndim == 2:
            img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
        return img
    return img if img.ndim == 2 else cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
