"""Quick check of the serving segmenter on N cached photos: Dice vs expert union mask + time.

Run:  python -m research.seg_check [N]
"""

from __future__ import annotations

import glob
import os
import sys
import time

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from hemosense.segment import segment_conjunctiva  # noqa: E402
from research.live_path_sim import sim_box  # noqa: E402


def main(n: int = 60) -> None:
    files = sorted(glob.glob(os.path.join(ROOT, "research", "data", "cache", "*.npz")))
    rng = np.random.default_rng(7)
    sel = rng.choice(len(files), min(n, len(files)), replace=False)
    ds, fails, t = [], 0, 0.0
    for i in sel:
        d = np.load(files[i])
        box = sim_box(d["union"], rng)
        t0 = time.time()
        res = segment_conjunctiva(d["img"], box)
        t += time.time() - t0
        if not res.ok:
            fails += 1
            continue
        g = d["union"]
        ds.append(2 * (g & res.mask).sum() / (g.sum() + res.mask.sum()))
    print(f"n={len(sel)} median dice {np.median(ds):.3f} mean {np.mean(ds):.3f} "
          f"p10 {np.percentile(ds, 10):.3f} fails {fails} avg {t / len(sel):.2f}s/photo")


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 60)
