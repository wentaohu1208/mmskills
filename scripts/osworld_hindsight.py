"""M3+M4 - PEEU Stage-2: planning experience utilization (hindsight).

Consumes M2's exploration trajectories (osworld_explorer.py output) and, faithful
to PEEU Eq.3-5:
  M3 (Eq.3-4) experience extraction: for each step compare before/after state
     (screenshot + a11y diff) + action -> atomic experience e_t; mu = (e_1..e_T).
  M4 (Eq.5)   aggregation Phi: fuse mu into ONE aligned, constrained high-level
     task d_tilde (success-by-construction: the task is what the trajectory did).

No VM needed (only reads files + calls the LLM). Endpoint from env:
  OPENAI_BASE_URL, OPENAI_API_KEY, OSWORLD_PROPOSER_MODEL (default 'gpt-5.5').

Run:
  python osworld_hindsight.py --traj explore_out/chrome_trajectories.jsonl \
      --out explore_out/chrome_peeu_tasks.jsonl --min-steps 2
"""

from __future__ import annotations

import argparse
import base64
import json
import logging
import os
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import requests

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

A11Y_DIFF_LINES = 60
A11Y_LINE_CHARS = 200


@dataclass(frozen=True)
class HindsightConfig:
    traj_path: str
    out_path: str
    model: str
    temperature: float
    min_steps: int
    reuse_path: Optional[str] = None


# ---------- GPT-5.5 (vision) ----------

def _img_block(png_bytes: bytes) -> Dict[str, Any]:
    uri = "data:image/png;base64," + base64.b64encode(png_bytes).decode("utf-8")
    return {"type": "image_url", "image_url": {"url": uri}}


def call_gpt(messages: List[Dict[str, Any]], cfg: HindsightConfig, retries: int = 5) -> str:
    base_url = os.environ["OPENAI_BASE_URL"].rstrip("/")
    api_key = os.environ["OPENAI_API_KEY"]
    last_err: Optional[Exception] = None
    for attempt in range(1, retries + 1):
        try:
            resp = requests.post(
                f"{base_url}/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={"model": cfg.model, "messages": messages, "temperature": cfg.temperature},
                timeout=180,
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]
        except (requests.RequestException, KeyError, IndexError, ValueError) as e:
            last_err = e
            logger.warning("gpt attempt %d/%d failed: %s", attempt, retries, e)
            if attempt < retries:
                time.sleep(min(5 * attempt, 30))
    raise RuntimeError(f"gpt failed after {retries} attempts: {last_err}")


# ---------- file helpers ----------

def _read_bytes(path: str) -> Optional[bytes]:
    try:
        with open(path, "rb") as fh:
            return fh.read()
    except OSError:
        return None


def _read_text(path: str) -> str:
    try:
        with open(path, encoding="utf-8") as fh:
            return fh.read()
    except OSError:
        return ""


def _write_jsonl(path: str, rows: List[Dict[str, Any]]) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")


def _empty_task() -> Dict[str, Any]:
    return {"task": "", "plan": [], "constraints": [], "observations": [],
            "verdict": "clean", "verdict_reason": ""}


def _a11y_diff(before_path: str, after_path: str) -> str:
    """Compact line-set diff of two a11y dumps (captures off-screen state change)."""
    before, after = _read_text(before_path), _read_text(after_path)
    if not before or not after:
        return ""
    bset = set(before.splitlines())
    added = [ln[:A11Y_LINE_CHARS] for ln in after.splitlines() if ln and ln not in bset][:A11Y_DIFF_LINES]
    aset = set(after.splitlines())
    removed = [ln[:A11Y_LINE_CHARS] for ln in before.splitlines() if ln and ln not in aset][:A11Y_DIFF_LINES]
    if not added and not removed:
        return ""
    return "A11Y ADDED:\n" + "\n".join(added) + "\nA11Y REMOVED:\n" + "\n".join(removed)


# ---------- M3: per-step experience extraction (Eq.3-4) ----------

def extract_experience(action: str, before_png: Optional[bytes], after_png: Optional[bytes],
                       a11y_diff: str, cfg: HindsightConfig) -> str:
    system = (
        "You compare the screen BEFORE and AFTER a GUI action and describe, in ONE sentence, what the "
        "action ACCOMPLISHED and the concrete target VALUE it set or required (the text typed, the "
        "filename/path chosen, the cell/value entered, the option selected). Do NOT enumerate ambient UI "
        "state the action did not change: no full dropdown/menu listings, no default dialog settings, no "
        "incidental counts. Return ONLY the sentence."
    )
    content: List[Dict[str, Any]] = [{"type": "text", "text": f"ACTION: {action}\n(before, then after)"}]
    if before_png:
        content.append(_img_block(before_png))
    if after_png:
        content.append(_img_block(after_png))
    if a11y_diff:
        content.append({"type": "text", "text": "Off-screen changes:\n" + a11y_diff})
    raw = call_gpt([{"role": "system", "content": system}, {"role": "user", "content": content}], cfg)
    return raw.strip().split("\n")[0][:300]


def m3_extract(traj: Dict[str, Any], cfg: HindsightConfig) -> List[str]:
    d = traj["dir"]
    steps = traj["steps"]
    mu: List[str] = []
    for i, st in enumerate(steps):
        before = _read_bytes(os.path.join(d, st.get("img_before", "")))
        after_name = steps[i + 1]["img_before"] if i + 1 < len(steps) else "final.png"
        after = _read_bytes(os.path.join(d, after_name))
        a11y = _a11y_diff(os.path.join(d, st.get("a11y_before", "")),
                          os.path.join(d, steps[i + 1].get("a11y_before", "")) if i + 1 < len(steps) else "")
        eps = extract_experience(st["action"], before, after, a11y, cfg)
        st["experience"] = eps
        mu.append(eps)
    return mu


# ---------- M4: aggregate mu -> aligned constrained task (Eq.5) ----------

def m4_synthesize(goal: str, actions: List[str], mu: List[str], cfg: HindsightConfig) -> Dict[str, Any]:
    system = (
        "You are given an agent's exploration of a desktop app: its loose original goal, the action "
        "sequence, and the per-step experiences (what each action did + concrete values). Synthesize ONE "
        "high-level task that this trajectory ACTUALLY accomplishes. Requirements:\n"
        "(1) ALIGNED - it must match what the trajectory really did, not the loose goal.\n"
        "(2) CONSTRAINED - 'constraints' lists ONLY the checkable success conditions the task itself "
        "requires (target values a user would specify: entered text/values, filenames/paths, formats, the "
        "final cell/selection/state that defines completion). Ambient UI state does NOT belong in "
        "'constraints' - full dropdown/menu contents, default dialog settings, incidental counts, or "
        "pre-existing app state go in 'observations'.\n"
        "(3) VERDICT - judge the outcome: 'degenerate_error' if the only outcome is an error/failure state "
        "(cannot connect/open, stuck); 'degenerate_noop' if it accomplishes nothing (opens then dismisses, "
        "verifies emptiness, fails to perform the intended change); 'navigation_only' if the end state is "
        "merely reaching a UI location (a menu/panel/dialog opened, a tool selected, a view/tab switched, an "
        "app launched) WITHOUT producing or editing content, applying a setting, or saving/exporting a file; "
        "otherwise 'clean'.\n"
        'Return ONLY JSON {"task": "...", "plan": ["..."], "constraints": ["..."], "observations": ["..."], '
        '"verdict": "clean|degenerate_error|degenerate_noop|navigation_only", "verdict_reason": "..."}.'
    )
    body = (
        f"ORIGINAL LOOSE GOAL: {goal}\n\nACTIONS:\n" + "\n".join(f"{i+1}. {a}" for i, a in enumerate(actions)) +
        "\n\nSTEP EXPERIENCES:\n" + "\n".join(f"{i+1}. {e}" for i, e in enumerate(mu)) +
        "\n\nSynthesize the aligned, constrained task as JSON."
    )
    raw = call_gpt([{"role": "system", "content": system}, {"role": "user", "content": body}], cfg)
    start = raw.find("{")
    if start == -1:
        return _empty_task()
    try:  # raw_decode: first JSON object only, ignore trailing garbage
        obj, _ = json.JSONDecoder().raw_decode(raw[start:])
    except json.JSONDecodeError:
        return _empty_task()
    if not isinstance(obj, dict):
        return _empty_task()
    verdict = str(obj.get("verdict", "clean")).strip() or "clean"
    if verdict not in ("clean", "degenerate_error", "degenerate_noop", "navigation_only"):
        verdict = "clean"
    return {"task": str(obj.get("task", "")).strip(),
            "plan": [str(p) for p in obj.get("plan", []) if isinstance(p, str)],
            "constraints": [str(c) for c in obj.get("constraints", []) if isinstance(c, str)],
            "observations": [str(o) for o in obj.get("observations", []) if isinstance(o, str)],
            "verdict": verdict,
            "verdict_reason": str(obj.get("verdict_reason", "")).strip()}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--traj", required=True, help="M2 trajectories jsonl")
    parser.add_argument("--out", required=True, help="output peeu_tasks jsonl")
    parser.add_argument("--temperature", type=float, default=0.7)
    parser.add_argument("--min-steps", type=int, default=2)
    parser.add_argument("--reuse-experiences", default=None,
                        help="old peeu_tasks jsonl: reuse its saved experiences (skip M3, M4-only re-run)")
    args = parser.parse_args()

    if not os.environ.get("OPENAI_BASE_URL") or not os.environ.get("OPENAI_API_KEY"):
        raise SystemExit("set OPENAI_BASE_URL and OPENAI_API_KEY in env")

    cfg = HindsightConfig(traj_path=args.traj, out_path=args.out,
                          model=os.environ.get("OSWORLD_PROPOSER_MODEL", "gpt-5.5"),
                          temperature=args.temperature, min_steps=args.min_steps,
                          reuse_path=args.reuse_experiences)

    try:
        with open(cfg.traj_path, encoding="utf-8") as fh:
            trajs = [json.loads(l) for l in fh if l.strip()]
    except FileNotFoundError:
        raise SystemExit(f"trajectory file not found: {cfg.traj_path}")

    # M4-only mode: reuse saved per-step experiences (mu) from a prior peeu_tasks file,
    # keyed by trajectory_dir, so M3 (per-step vision) is skipped and only M4 re-runs.
    reuse_mu: Dict[str, List[str]] = {}
    if cfg.reuse_path:
        try:
            with open(cfg.reuse_path, encoding="utf-8") as fh:
                for line in fh:
                    if not line.strip():
                        continue
                    rec = json.loads(line)
                    d, mu = rec.get("trajectory_dir"), rec.get("experiences")
                    if d and isinstance(mu, list):
                        reuse_mu[d] = [str(x) for x in mu]
            logger.info("reuse-experiences: loaded %d cached mu from %s", len(reuse_mu), cfg.reuse_path)
        except FileNotFoundError:
            raise SystemExit(f"reuse-experiences file not found: {cfg.reuse_path}")
    clean: List[Dict[str, Any]] = []
    degenerate: List[Dict[str, Any]] = []
    trivial: List[Dict[str, Any]] = []
    for tj in trajs:
        if tj.get("n_steps", 0) < cfg.min_steps:
            logger.info("skip %s (only %d steps)", tj.get("goal", "")[:40], tj.get("n_steps", 0))
            continue
        try:
            mu = reuse_mu.get(tj["dir"]) or m3_extract(tj, cfg)
            actions = [s["action"] for s in tj["steps"]]
            d_tilde = m4_synthesize(tj["goal"], actions, mu, cfg)
        except Exception as e:  # one trajectory failure must not kill the batch
            logger.error("hindsight failed for %s: %s", tj.get("goal", "")[:40], e)
            continue
        if not d_tilde["task"]:
            continue
        rec = {**d_tilde, "original_goal": tj["goal"], "app": tj["app"],
               "n_steps": tj["n_steps"], "end_reason": tj.get("end_reason"),
               "experiences": mu, "trajectory_dir": tj["dir"]}
        v = d_tilde["verdict"]
        (clean if v == "clean" else trivial if v == "navigation_only" else degenerate).append(rec)
        logger.info("[%s|%s] -> %s", tj["app"], v, d_tilde["task"][:70])

    root, ext = os.path.splitext(cfg.out_path)
    ext = ext or ".jsonl"
    deg_path = f"{root}_degenerate{ext}"
    trivial_path = f"{root}_trivial{ext}"
    _write_jsonl(cfg.out_path, clean)
    _write_jsonl(deg_path, degenerate)
    _write_jsonl(trivial_path, trivial)
    logger.info("wrote %d clean -> %s | %d degenerate -> %s | %d trivial -> %s",
                len(clean), cfg.out_path, len(degenerate), deg_path, len(trivial), trivial_path)
    logger.info("NEXT: feed the CLEAN aligned tasks+trajectories to skill-summarization + self-OPD.")


if __name__ == "__main__":
    main()
