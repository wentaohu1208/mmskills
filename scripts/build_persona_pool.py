"""Build a light-filtered persona pool (personas.txt) from Tencent Persona Hub for explore rollouts.

STREAMS one shard of Persona Hub's ElitePersonas (proj-persona/PersonaHub) -- stopping after a few
MB, since we keep only a small pool -- keeps personas whose text signals DESK / knowledge / creative
/ technical work (the apps we explore are LibreOffice / GIMP / VS Code), collapses whitespace,
length-caps, dedups, and writes N personas one-per-line. Deterministic (seeded shuffle) -> reproducible.

Single shared pool for all apps; per-app mismatch is handled downstream by the goal-proposal prompt
("adopt the persona WHERE it fits; do NOT force a weird fit"). Basis: Persona Hub (2406.20094);
usage aligns AgentSynth (2506.14205, persona-seeded task proposal).

Run (remote, proxy needed for HF):
  HTTPS_PROXY=http://127.0.0.1:7897 /data/hwt/envs/mmskills/bin/python build_persona_pool.py \
      --out /data/hwt/OSWorld/personas.txt --n 120
"""

from __future__ import annotations

import argparse
import json
import logging
import random
import re
from typing import List

import requests
from huggingface_hub import hf_hub_url

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

_REPO = "proj-persona/PersonaHub"
_SHARD = "ElitePersonas/elite_personas.part1.jsonl"
_TEXT_KEYS = ("persona", "input persona", "elite_persona", "text")
# LIGHT allow-list: whole-word role/topic signals that plausibly use a desktop office/creative/dev app.
# Inclusive by design -- the goal is only to drop personas that would essentially never touch a computer.
_DESK_RE = re.compile(
    r"\b(analyst|manager|director|teacher|professor|lecturer|tutor|instructor|educator|student|"
    r"writer|author|editor|journalist|blogger|copywriter|translator|"
    r"designer|developer|programmer|engineer|architect|coder|"
    r"accountant|auditor|bookkeeper|"
    r"researcher|scientist|economist|statistician|mathematician|academic|scholar|"
    r"marketer|consultant|administrator|assistant|secretary|clerk|coordinator|planner|strategist|"
    r"entrepreneur|founder|executive|artist|photographer|illustrator|animator|"
    r"librarian|recruiter|technician|specialist|"
    r"finance|financial|marketing|business|accounting|"
    r"software|programming|data)\b",
    re.IGNORECASE,
)


def _persona_text(rec: dict) -> str:
    """Extract the persona description; try known keys, else the first non-empty string value."""
    for k in _TEXT_KEYS:
        v = rec.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    for v in rec.values():
        if isinstance(v, str) and v.strip():
            return v.strip()
    return ""


def load_raw(scan: int) -> List[str]:
    """STREAM the shard (it is ~256MB+) and stop after `scan` raw personas -- we only keep a small pool,
    so reading the first few MB is enough and avoids pulling the whole file."""
    url = hf_hub_url(_REPO, _SHARD, repo_type="dataset")
    out: List[str] = []
    with requests.get(url, stream=True, timeout=60) as resp:  # HTTPS_PROXY honoured from env
        resp.raise_for_status()
        for raw_line in resp.iter_lines(decode_unicode=True):
            if not raw_line:
                continue
            try:
                rec = json.loads(raw_line)
            except json.JSONDecodeError:
                continue
            txt = _persona_text(rec)
            if txt:
                out.append(txt)
            if len(out) >= scan:
                break
    return out


def build(raw: List[str], n: int, seed: int) -> List[str]:
    """Deterministically shuffle, light-filter to desk-plausible personas, dedup + length-cap, take N."""
    rng = random.Random(seed)
    order = list(raw)
    rng.shuffle(order)
    seen: set = set()
    kept: List[str] = []
    for p in order:
        p = " ".join(p.split())[:200]  # collapse whitespace + cap length (bounds prompt-injection surface)
        if p in seen or not _DESK_RE.search(p):
            continue
        seen.add(p)
        kept.append(p)
        if len(kept) >= n:
            break
    return kept


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True, help="output personas.txt (one persona per line)")
    ap.add_argument("--n", type=int, default=120, help="target pool size")
    ap.add_argument("--scan", type=int, default=8000, help="raw personas to stream before filtering")
    ap.add_argument("--seed", type=int, default=42, help="shuffle seed (reproducibility)")
    args = ap.parse_args()
    if args.n < 1:
        ap.error("--n must be >= 1")

    raw = load_raw(args.scan)
    logger.info("streamed %d raw personas from %s", len(raw), _SHARD)
    kept = build(raw, args.n, args.seed)
    if not kept:
        raise SystemExit("no personas kept after filtering -- check the shard schema / allow-list")
    with open(args.out, "w", encoding="utf-8") as fh:
        fh.write("\n".join(kept) + "\n")
    logger.info("wrote %d filtered personas (of target %d) -> %s", len(kept), args.n, args.out)
    logger.info("sample: %s", " | ".join(k[:50] for k in kept[:3]))


if __name__ == "__main__":
    main()
