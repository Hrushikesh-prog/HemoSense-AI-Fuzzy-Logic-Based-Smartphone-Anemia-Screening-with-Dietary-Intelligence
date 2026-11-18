"""
rag_eval.py
With-vs-without-RAG comparison of the Dietary Intelligence output (same model, same prompt;
the only difference is the retrieved guideline excerpts).

Run (from the repo root):
    python -m research.rag_eval                     # 20 profiles x 2 arms
    python -m research.rag_eval --n 6               # quick smoke run

Writes research/results_rag/{outputs.jsonl, per_profile.csv, summary.md}.

Scoring is deterministic (reproducible, no LLM judge):
  - guideline_coverage: share of the profile's applicable checklist items the answer mentions
    (checklist below, derived from ICMR-NIN / Anemia Mukt Bharat / WHO guidance)
  - citations: number of inline [S#] citations; invalid_citations: [S#] not in the retrieved set
  - disclaimer: required closing disclaimer present
Spot-check a sample by hand before reporting; keyword matching can miss paraphrases.
"""

import argparse
import csv
import itertools
import json
import os
import re
import statistics
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from api import config, llm  # noqa: E402

OUT_DIR = os.path.join(ROOT, "research", "results_rag")

# item -> (applies(profile) -> bool, regex any-of)
CHECKLIST = {
    "iron_rich_plant_foods": (lambda p: True,
                              r"green leafy|spinach|palak|amaranth|drumstick|moringa|pulses|dal|legume|ragi|millet|jaggery"),
    "vitamin_c_pairing": (lambda p: True, r"vitamin c|amla|guava|lemon|citrus|orange"),
    "tea_coffee_timing": (lambda p: True, r"\btea\b|coffee"),
    "ifa_supplement": (lambda p: p["severity"] != "Normal",
                       r"\bifa\b|iron[- ]folic|iron tablet|iron supplement|folic acid"),
    "clinician_referral": (lambda p: True, r"doctor|clinician|health ?care|phc|referr|physician|health worker"),
    "urgent_for_severe": (lambda p: p["severity"] in ("Moderate", "Severe"),
                          r"urgent|immediately|as soon as|promptly|without delay|right away"),
    "pregnancy_specific": (lambda p: p.get("pregnant"), r"pregnan|antenatal|anc\b|trimester"),
    "vegetarian_respected": (lambda p: p["diet"] in ("vegetarian", "vegan"),
                             r"vegetarian|vegan|plant[- ]based"),
    "heme_sources": (lambda p: p["diet"] == "omnivore", r"meat|liver|fish|chicken|egg|mutton|heme"),
}
DISCLAIMER_RE = r"does not replace medical advice"


def profiles(n):
    sev = ["Normal", "Mild", "Moderate", "Severe"]
    who = [
        {"sex": "female", "age": 24, "pregnant": False},
        {"sex": "female", "age": 27, "pregnant": True},
        {"sex": "male", "age": 35, "pregnant": False},
        {"sex": "female", "age": 15, "pregnant": False},
    ]
    diets = ["vegetarian", "omnivore", "vegan"]
    regions = ["Andhra Pradesh", "Maharashtra", "Uttar Pradesh", "Tamil Nadu", "West Bengal"]
    out = []
    for i, (s, w, d) in enumerate(itertools.product(sev, who, diets)):
        out.append({"id": i, "severity": s, "diet": d, "region": regions[i % len(regions)], **w})
    # fixed-seed sample, balanced across severity (reproducible)
    import random
    rng = random.Random(42)
    by_sev = {s: [p for p in out if p["severity"] == s] for s in sev}
    for lst in by_sev.values():
        rng.shuffle(lst)
    picked = [by_sev[sev[i % 4]][i // 4] for i in range(min(n, len(out)))]
    return sorted(picked, key=lambda p: p["id"])


def payload_for(p):
    return {
        "screening": {"severity_class": p["severity"], "anemic": p["severity"] != "Normal"},
        "user_context": {"age": p["age"], "sex": p["sex"], "pregnant": p["pregnant"],
                         "diet": p["diet"], "region": p["region"]},
    }


def score(p, text, n_sources):
    low = text.lower()
    items = {k: bool(re.search(rx, low)) for k, (applies, rx) in CHECKLIST.items() if applies(p)}
    cites = [int(c) for c in re.findall(r"\[S(\d+)\]", text)]
    return {
        "coverage": sum(items.values()) / len(items),
        "items": items,
        "citations": len(cites),
        "invalid_citations": sum(1 for c in cites if c < 1 or c > n_sources),
        "disclaimer": bool(re.search(DISCLAIMER_RE, low)),
        "chars": len(text),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=20)
    args = ap.parse_args()
    if not os.path.exists(config.RAG_INDEX_PATH):
        raise SystemExit(f"RAG index missing: {config.RAG_INDEX_PATH}")
    os.makedirs(OUT_DIR, exist_ok=True)

    rows = []
    with open(os.path.join(OUT_DIR, "outputs.jsonl"), "w", encoding="utf-8") as fh:
        for p in profiles(args.n):
            for arm in ("no_rag", "rag"):
                t0 = time.time()
                try:
                    r = llm.generate_recommendations(payload_for(p), use_rag=(arm == "rag"))
                except llm.LlmError as exc:
                    print(f"profile {p['id']} {arm}: FAILED {exc.message}")
                    continue
                sc = score(p, r["recommendations"], len(r["sources"]))
                rec = {"profile": p, "arm": arm, "model": r["model_used"],
                       "seconds": round(time.time() - t0, 1), "score": sc,
                       "sources": r["sources"], "text": r["recommendations"]}
                fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
                rows.append(rec)
                print(f"profile {p['id']:>2} {arm:6} cov={sc['coverage']:.2f} cites={sc['citations']} "
                      f"model={r['model_used']}")

    with open(os.path.join(OUT_DIR, "per_profile.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["profile", "severity", "sex", "pregnant", "diet", "arm", "model", "coverage",
                    "citations", "invalid_citations", "disclaimer", "chars"])
        for r in rows:
            p, s = r["profile"], r["score"]
            w.writerow([p["id"], p["severity"], p["sex"], p["pregnant"], p["diet"], r["arm"], r["model"],
                        f"{s['coverage']:.3f}", s["citations"], s["invalid_citations"],
                        int(s["disclaimer"]), s["chars"]])

    def agg(arm):
        rs = [r for r in rows if r["arm"] == arm]
        if not rs:
            return None
        cov = [r["score"]["coverage"] for r in rs]
        return {
            "n": len(rs),
            "coverage_mean": statistics.mean(cov),
            "coverage_sd": statistics.pstdev(cov),
            "with_citation": sum(r["score"]["citations"] > 0 for r in rs) / len(rs),
            "citations_mean": statistics.mean(r["score"]["citations"] for r in rs),
            "invalid_citations": sum(r["score"]["invalid_citations"] for r in rs),
            "disclaimer": sum(r["score"]["disclaimer"] for r in rs) / len(rs),
            "models": sorted({r["model"] for r in rs}),
        }

    a, b = agg("no_rag"), agg("rag")
    paired = {}
    for r in rows:
        paired.setdefault(r["profile"]["id"], {})[r["arm"]] = r["score"]["coverage"]
    diffs = [v["rag"] - v["no_rag"] for v in paired.values() if len(v) == 2]
    better = sum(d > 0 for d in diffs)
    worse = sum(d < 0 for d in diffs)

    lines = ["# RAG vs no-RAG: Dietary Intelligence", "",
             f"Index: `{os.path.relpath(config.RAG_INDEX_PATH, ROOT)}`, top-k = {config.RAG_TOP_K}. "
             f"Profiles: {len(paired)}. Same model and prompt in both arms.", "",
             "| Metric | No RAG | RAG |", "|---|---|---|"]
    if a and b:
        lines += [
            f"| Guideline checklist coverage (mean ± SD) | {a['coverage_mean']:.2f} ± {a['coverage_sd']:.2f} "
            f"| {b['coverage_mean']:.2f} ± {b['coverage_sd']:.2f} |",
            f"| Answers citing a guideline source | {a['with_citation']:.0%} | {b['with_citation']:.0%} |",
            f"| Citations per answer (mean) | {a['citations_mean']:.1f} | {b['citations_mean']:.1f} |",
            f"| Invalid citations (total) | {a['invalid_citations']} | {b['invalid_citations']} |",
            f"| Disclaimer present | {a['disclaimer']:.0%} | {b['disclaimer']:.0%} |",
            f"| Model(s) | {', '.join(a['models'])} | {', '.join(b['models'])} |",
            "",
            f"Paired coverage difference (RAG − no RAG): mean {statistics.mean(diffs):+.3f}; "
            f"RAG better on {better}, worse on {worse}, tied on {len(diffs) - better - worse} profiles.",
        ]
    lines += ["", "Coverage = share of the applicable checklist items mentioned (keyword match; "
              "see CHECKLIST in research/rag_eval.py). Spot-check outputs.jsonl before reporting."]
    with open(os.path.join(OUT_DIR, "summary.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
