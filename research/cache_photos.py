"""Cache each participant's photo at the serving working resolution plus the expert
palpebral and forniceal+palpebral masks (same resolution) -> research/data/cache/<pid>.npz.

Run:  python -m research.cache_photos
"""

from __future__ import annotations

import glob
import os
import sys

import cv2
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from hemosense.data import load_participants  # noqa: E402
from hemosense.features import mask_from_rgba  # noqa: E402
from hemosense.segment import _working  # noqa: E402

CACHE = os.path.join(ROOT, "research", "data", "cache")


def main() -> None:
    os.makedirs(CACHE, exist_ok=True)
    df, _ = load_participants()
    for i, r in enumerate(df.itertuples()):
        out = os.path.join(CACHE, f"{r.pid}.npz")
        if os.path.exists(out) or not isinstance(r.photo, str):
            continue
        img = _working(cv2.imread(r.photo))
        H, W = img.shape[:2]

        def m(path):
            mk = mask_from_rgba(cv2.imread(path, cv2.IMREAD_UNCHANGED)).astype(np.uint8)
            return cv2.resize(mk, (W, H), interpolation=cv2.INTER_NEAREST).astype(bool)

        palp = m(r.palpebral_png)
        u = glob.glob(os.path.join(os.path.dirname(r.palpebral_png), "*forniceal_palpebral.png"))
        union = m(u[0]) if u else palp
        np.savez_compressed(out, img=img, palp=palp, union=union | palp)
        if (i + 1) % 25 == 0:
            print(f"  {i + 1}/{len(df)}", flush=True)
    print("done")


if __name__ == "__main__":
    main()
