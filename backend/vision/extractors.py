"""Measurement extractors, one plugin per camera view. Thresholds are parameters.

BacklitDroplet: background subtraction → threshold → largest dark blob → equivalent-circle
diameter (sub-pixel, from partial pixel coverage) + ellipse fit.
Flame: luminosity threshold → outer diameter, mean/peak intensity, red/blue ratio (soot proxy).
"""
from __future__ import annotations

from dataclasses import dataclass, field

import cv2
import numpy as np


@dataclass
class BacklitDroplet:
    name: str = "backlit_droplet"
    version: str = "1.1.0"
    params: dict = field(default_factory=lambda: {"threshold": 0.5, "roi": None, "min_area_px": 6})

    def measure(self, gray: np.ndarray, px_per_mm: float) -> dict:
        p = self.params
        img = gray.astype(np.float32)
        x0 = y0 = 0
        if p.get("roi"):
            x0, y0, w, h = [int(v) for v in p["roi"]]
            img = img[y0:y0 + h, x0:x0 + w]
        # background: median of the frame border (backlight); foreground: darkest robust level
        border = np.concatenate([img[0], img[-1], img[:, 0], img[:, -1]])
        bg = float(np.median(border))
        fg = float(np.percentile(img, 0.5))
        contrast = bg - fg
        if contrast < 15:
            return {"ok": False, "reason": "no dark object (contrast < 15)"}
        cover = np.clip((bg - img) / contrast, 0, 1)                   # background subtraction, normalized
        mask = (cover >= p.get("threshold", 0.5)).astype(np.uint8)
        n, lab, stats, cent = cv2.connectedComponentsWithStats(mask, 8)
        if n <= 1:
            return {"ok": False, "reason": "no blob above threshold"}
        i = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
        if stats[i, cv2.CC_STAT_AREA] < p.get("min_area_px", 6):
            return {"ok": False, "reason": "blob too small"}
        blob = (lab == i).astype(np.uint8)
        # refine the foreground level from the blob core (robust to noise), then recompute coverage
        core = cv2.erode(blob, np.ones((5, 5), np.uint8))
        if core.sum() >= 4:
            fg = float(np.median(img[core > 0]))
            contrast = bg - fg
            cover = np.clip((bg - img) / contrast, 0, 1)
        region = cv2.dilate(blob, np.ones((5, 5), np.uint8))
        area = float((cover * region).sum())                            # sub-pixel area from coverage
        d_px = 2 * np.sqrt(area / np.pi)
        cnts, _ = cv2.findContours(blob, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        c = max(cnts, key=cv2.contourArea)
        perim = cv2.arcLength(c, True)
        circ = float(4 * np.pi * cv2.contourArea(c) / perim ** 2) if perim > 0 else 0.0
        ell = None
        if len(c) >= 5:
            (ex, ey), (ma, mi), ang = cv2.fitEllipse(c)
            ell = {"cx": ex + x0, "cy": ey + y0, "major_mm": max(ma, mi) / px_per_mm, "minor_mm": min(ma, mi) / px_per_mm,
                   "angle": ang}
        cx, cy = cent[i]
        conf = float(np.clip(contrast / 120, 0, 1) * np.clip(circ, 0, 1) ** 0.5 * (1.0 if d_px > 8 else d_px / 8))
        step = max(1, len(c) // 48)
        return {"ok": True, "droplet_diameter_mm": d_px / px_per_mm, "cx": float(cx + x0), "cy": float(cy + y0),
                "d_px": d_px, "circularity": circ, "ellipse": ell, "confidence": round(conf, 3),
                "contour": (c[::step, 0, :] + [x0, y0]).tolist(), "contrast": contrast}


@dataclass
class Flame:
    name: str = "flame_luminosity"
    version: str = "1.0.0"
    params: dict = field(default_factory=lambda: {"floor": 18, "rel_threshold": 0.25, "roi": None})

    def measure(self, bgr: np.ndarray, px_per_mm: float) -> dict:
        p = self.params
        x0 = y0 = 0
        img = bgr
        if p.get("roi"):
            x0, y0, w, h = [int(v) for v in p["roi"]]
            img = img[y0:y0 + h, x0:x0 + w]
        lum = img.max(axis=2).astype(np.float32) if img.ndim == 3 else img.astype(np.float32)
        peak = float(np.percentile(lum, 99.9))
        mean_all = float(lum.mean())
        if peak < p.get("floor", 18):
            return {"ok": True, "lit": False, "peak_intensity": peak, "mean_intensity": mean_all, "confidence": 0.9}
        thr = max(p.get("floor", 18), p.get("rel_threshold", 0.25) * peak)
        mask = (lum >= thr).astype(np.uint8)
        cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not cnts:
            return {"ok": True, "lit": False, "peak_intensity": peak, "mean_intensity": mean_all, "confidence": 0.5}
        c = max(cnts, key=cv2.contourArea)
        filled = np.zeros_like(mask)
        cv2.drawContours(filled, [c], -1, 1, -1)
        area = float(filled.sum())
        d_px = 2 * np.sqrt(area / np.pi)
        M = cv2.moments(c)
        cx = M["m10"] / M["m00"] if M["m00"] else lum.shape[1] / 2
        cy = M["m01"] / M["m00"] if M["m00"] else lum.shape[0] / 2
        inside = lum[filled > 0]
        rb = None
        if img.ndim == 3:
            b, r = img[..., 0][filled > 0].astype(float), img[..., 2][filled > 0].astype(float)
            rb = float(r.mean() / max(b.mean(), 1.0))
        step = max(1, len(c) // 48)
        return {"ok": True, "lit": True, "flame_diameter_mm": d_px / px_per_mm, "cx": cx + x0, "cy": cy + y0,
                "peak_intensity": peak, "mean_intensity": float(inside.mean()), "red_blue_ratio": rb,
                "confidence": round(float(np.clip((peak - thr) / 120, 0.2, 1.0)), 3),
                "contour": (c[::step, 0, :] + [x0, y0]).tolist()}


EXTRACTORS = {"backlit": BacklitDroplet, "flame": Flame}
