"""
rag.py
Retrieval for the Dietary Intelligence endpoint (RAG over Indian/WHO anaemia guidance).

Offline (once):  python -m hemosense.rag build research/rag_sources models/rag_index.json
  - reads every PDF/TXT/MD in the folder, splits it into ~900-character chunks with
    page numbers, and writes a JSON index (no external service, no cost).
  - optional research/rag_sources/sources.json: {"file.pdf": "Readable source title", ...}

Online (per request): Index.search(query, k) -> top-k chunks by BM25 (lexical ranking).
  Pure Python, so retrieval adds milliseconds and cannot fail because of a network call.

Check a query:   python -m hemosense.rag search models/rag_index.json "iron rich vegetarian pregnancy"
"""

import json
import math
import os
import re
import sys
from collections import Counter

CHUNK_CHARS = 900
CHUNK_OVERLAP = 150
_TOKEN_RE = re.compile(r"[a-z0-9]+")
_STOP = set("""a an and are as at be by for from has have in is it its of on or that the this to
was were will with which their these those than then there can may should not no also into such
per who all any been being but if more most other some only over under up out so very""".split())


def tokenize(text: str):
    return [t for t in _TOKEN_RE.findall(text.lower()) if t not in _STOP and len(t) > 1]


# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------
def _clean(text: str) -> str:
    text = text.replace("­", "")                 # soft hyphens
    text = re.sub(r"-\n(?=[a-z])", "", text)         # words hyphenated across lines
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{2,}", "\n", text)
    return text.strip()


def _pages(path: str):
    """Yields (page_number, text). Page is None for plain-text sources."""
    ext = os.path.splitext(path)[1].lower()
    if ext == ".pdf":
        from pypdf import PdfReader
        reader = PdfReader(path)
        for i, page in enumerate(reader.pages, start=1):
            try:
                yield i, _clean(page.extract_text() or "")
            except Exception:  # noqa: BLE001 - one unreadable page should not stop the build
                continue
    elif ext in (".txt", ".md"):
        with open(path, encoding="utf-8", errors="ignore") as fh:
            yield None, _clean(fh.read())


def _split(text: str):
    """~CHUNK_CHARS pieces, broken at sentence ends where possible, with overlap."""
    out, start, n = [], 0, len(text)
    while start < n:
        end = min(start + CHUNK_CHARS, n)
        if end < n:
            cut = max(text.rfind(". ", start + CHUNK_CHARS // 2, end),
                      text.rfind("\n", start + CHUNK_CHARS // 2, end))
            if cut > start:
                end = cut + 1
        piece = text[start:end].strip()
        if len(piece) > 80:                           # drop headers/footers-only fragments
            out.append(piece)
        if end >= n:
            break
        start = max(end - CHUNK_OVERLAP, start + 1)
    return out


def build(src_dir: str, out_path: str) -> dict:
    titles = {}
    meta = os.path.join(src_dir, "sources.json")
    if os.path.exists(meta):
        with open(meta, encoding="utf-8") as fh:
            titles = json.load(fh)

    chunks = []
    for name in sorted(os.listdir(src_dir)):
        path = os.path.join(src_dir, name)
        if not os.path.isfile(path) or name == "sources.json":
            continue
        title = titles.get(name, os.path.splitext(name)[0].replace("_", " "))
        n_before = len(chunks)
        for page, text in _pages(path):
            for piece in _split(text):
                chunks.append({"id": len(chunks), "source": title, "file": name,
                               "page": page, "text": piece})
        print(f"  {name}: {len(chunks) - n_before} chunks")

    if not chunks:
        raise SystemExit(f"No text found in {src_dir} (PDF/TXT/MD expected).")
    index = {"version": 1, "chunk_chars": CHUNK_CHARS, "chunks": chunks}
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(index, fh, ensure_ascii=False)
    print(f"wrote {len(chunks)} chunks -> {out_path}")
    return index


# ---------------------------------------------------------------------------
# Search (BM25)
# ---------------------------------------------------------------------------
class Index:
    K1, B = 1.5, 0.75

    def __init__(self, chunks):
        self.chunks = chunks
        self._tf = [Counter(tokenize(c["text"])) for c in chunks]
        self._len = [sum(tf.values()) for tf in self._tf]
        self._avg = (sum(self._len) / len(self._len)) if self._len else 0.0
        df = Counter()
        for tf in self._tf:
            df.update(tf.keys())
        n = len(chunks)
        self._idf = {t: math.log(1 + (n - d + 0.5) / (d + 0.5)) for t, d in df.items()}

    @classmethod
    def load(cls, path: str):
        with open(path, encoding="utf-8") as fh:
            return cls(json.load(fh)["chunks"])

    def search(self, query: str, k: int = 5, per_source: int = 2):
        q = set(tokenize(query))
        scored = []
        for i, tf in enumerate(self._tf):
            s = 0.0
            for t in q:
                f = tf.get(t)
                if f:
                    norm = self.K1 * (1 - self.B + self.B * self._len[i] / (self._avg or 1))
                    s += self._idf[t] * f * (self.K1 + 1) / (f + norm)
            if s > 0:
                scored.append((s, i))
        scored.sort(reverse=True)
        n_sources = len({c["source"] for c in self.chunks}) or 1
        per_source = max(per_source, math.ceil(k / n_sources))   # few sources -> allow more each
        hits, seen = [], Counter()
        for s, i in scored:                           # keep sources diverse
            c = self.chunks[i]
            if seen[c["source"]] >= per_source:
                continue
            seen[c["source"]] += 1
            hits.append({**c, "score": round(s, 3)})
            if len(hits) >= k:
                break
        return hits


def query_for(payload: dict) -> str:
    """Builds a retrieval query from the screening result and the user's context."""
    scr = payload.get("screening") or {}
    ctx = payload.get("user_context") or {}
    sev = str(scr.get("severity_class") or "").lower()
    parts = ["iron deficiency anaemia anemia diet iron-rich foods vitamin C absorption"]
    if sev in ("normal", ""):
        parts.append("prevention adolescents women")
    else:
        parts.append(f"{sev} anaemia treatment iron folic acid IFA supplementation referral")
    if ctx.get("pregnant"):
        parts.append("pregnant pregnancy women antenatal")
    if ctx.get("sex"):
        parts.append("women" if str(ctx["sex"]).lower().startswith("f") else "men")
    if ctx.get("age") is not None:
        try:
            age = int(ctx["age"])
            parts.append("children" if age < 10 else "adolescents" if age < 20 else "adults")
        except (TypeError, ValueError):
            pass
    if ctx.get("diet"):
        parts.append(f"{ctx['diet']} vegetarian pulses green leafy vegetables millets")
    if ctx.get("region"):
        parts.append(str(ctx["region"]))
    return " ".join(parts)


if __name__ == "__main__":
    if len(sys.argv) >= 4 and sys.argv[1] == "build":
        build(sys.argv[2], sys.argv[3])
    elif len(sys.argv) >= 4 and sys.argv[1] == "search":
        for h in Index.load(sys.argv[2]).search(" ".join(sys.argv[3:])):
            print(f"[{h['score']}] {h['source']} p.{h['page']}: {h['text'][:160]!r}")
    else:
        print(__doc__)
