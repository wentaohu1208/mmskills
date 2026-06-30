"""Stage ① cleaning: collect 8B rollout episodes into one trajectory set.

Per the agreed spec this is a LIGHT pass — it only does two things:
  1. collect & organize each episode (actions + screenshots + matched PEEU reference)
  2. drop genuine empty shells (no data at all)

It does NOT judge quality: capability errors (misclick / stuck / unfinished) are
all KEPT. Environment-failure filtering is a finer pass done later by the judge
(stage ②), not here.

An episode is dropped ONLY if it is an empty shell, i.e. any of:
  - traj.jsonl missing / unreadable
  - no step screenshots on disk
  - not a single parseable action

Output: trajectories.jsonl, one line per kept episode:
  {task_id, round, domain, instruction, reference{constraints,plan,experiences},
   actions[], frames[], n_steps}

Run (offline, no API):
  python osworld_clean.py --rounds-glob 'rollout_8b/r[0-5]' \
      --tasks-glob 'explore_0629/*_peeu_tasks.jsonl' --out trajectories.jsonl
"""

from __future__ import annotations

import argparse
import glob
import hashlib
import json
import logging
import os
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# A step counts as "real" if its action contains a pyautogui call with a number,
# or a special token (DONE/WAIT/FAIL). Mirrors the rollout action format.
_COORD_RE = re.compile(r"pyautogui\.[A-Za-z]+\([^)]*\d")
_SPECIAL = ("DONE", "WAIT", "FAIL")
_STEP_RE = re.compile(r"step_(\d+)")


@dataclass(frozen=True)
class CleanConfig:
    rounds_glob: str
    tasks_glob: str
    out_path: str


def is_valid_action(action: str) -> bool:
    a = (action or "").strip()
    if not a:
        return False
    if any(s in a for s in _SPECIAL):
        return True
    return bool(_COORD_RE.search(a))


def build_ref_map(tasks_glob: str) -> Dict[str, Dict[str, Any]]:
    """Map md5(task)[:10] -> PEEU reference (constraints/plan/experiences/...)."""
    ref: Dict[str, Dict[str, Any]] = {}
    for f in sorted(glob.glob(tasks_glob)):
        for line in open(f, encoding="utf-8"):
            line = line.strip()
            if not line:
                continue
            try:
                t = json.loads(line)
            except json.JSONDecodeError:
                continue
            task = (t.get("task") or "").strip()
            if not task:
                continue
            h = hashlib.md5(task.encode()).hexdigest()[:10]
            ref[h] = {
                "instruction": task,
                "constraints": t.get("constraints") or [],
                "plan": t.get("plan") or [],
                "experiences": t.get("experiences") or [],
                "app": t.get("app"),
            }
    return ref


def load_actions(traj_path: str) -> Optional[List[Dict[str, Any]]]:
    """Read traj.jsonl into ordered step records; None if unreadable/empty."""
    if not os.path.exists(traj_path):
        return None
    steps: List[Dict[str, Any]] = []
    for line in open(traj_path, encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        try:
            s = json.loads(line)
        except json.JSONDecodeError:
            continue
        steps.append(s)
    return steps or None


def list_frames(ep_dir: str) -> List[str]:
    """Step screenshots in the episode dir, ordered by step number."""
    pngs = [p for p in os.listdir(ep_dir) if p.startswith("step_") and p.endswith(".png")]
    pngs.sort(key=lambda n: int(m.group(1)) if (m := _STEP_RE.search(n)) else -1)
    return pngs


def round_of(ep_dir: str) -> str:
    m = re.search(r"/(r\d)/", ep_dir + "/")
    return m.group(1) if m else "?"


def clean_one(ep_dir: str, ref_map: Dict[str, Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Return a cleaned record, or None to drop (empty shell)."""
    steps = load_actions(os.path.join(ep_dir, "traj.jsonl"))
    if steps is None:
        return None  # traj missing/unreadable
    frames = list_frames(ep_dir)
    if not frames:
        return None  # no screenshots
    actions = [(s.get("action") or "").strip() for s in steps]
    if not any(is_valid_action(a) for a in actions):
        return None  # not a single parseable action

    tid = os.path.basename(ep_dir)
    ref = ref_map.get(tid.split("-")[-1], {})
    parts = ep_dir.split("/qwen3vl8b/")[-1].split("/")
    domain = parts[0] if len(parts) >= 2 else ref.get("app", "?")
    return {
        "task_id": tid,
        "round": round_of(ep_dir),
        "domain": domain,
        "instruction": ref.get("instruction"),
        "reference": {
            "constraints": ref.get("constraints", []),
            "plan": ref.get("plan", []),
            "experiences": ref.get("experiences", []),
        },
        "actions": actions,
        "frames": frames,
        "n_steps": len(steps),
        "dir": ep_dir,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rounds-glob", default="rollout_8b/r[0-5]")
    ap.add_argument("--tasks-glob", default="explore_0629/*_peeu_tasks.jsonl")
    ap.add_argument("--out", default="trajectories.jsonl")
    args = ap.parse_args()

    cfg = CleanConfig(rounds_glob=args.rounds_glob, tasks_glob=args.tasks_glob, out_path=args.out)
    ref_map = build_ref_map(cfg.tasks_glob)
    logger.info("reference map: %d tasks", len(ref_map))

    dirs = sorted({os.path.dirname(p) for p in glob.glob(f"{cfg.rounds_glob}/**/traj.jsonl", recursive=True)})
    kept: List[Dict[str, Any]] = []
    dropped = 0
    no_ref = 0
    with open(cfg.out_path, "w", encoding="utf-8") as fout:
        for d in dirs:
            rec = clean_one(d, ref_map)
            if rec is None:
                dropped += 1
                continue
            if rec["instruction"] is None:
                no_ref += 1  # kept, but reference not matched (flag for review)
            kept.append(rec)
            fout.write(json.dumps(rec, ensure_ascii=False) + "\n")

    from collections import Counter
    by_round = Counter(r["round"] for r in kept)
    by_domain = Counter(r["domain"] for r in kept)
    logger.info("episode dirs scanned: %d", len(dirs))
    logger.info("kept: %d | dropped empty shells: %d | kept-but-no-reference: %d", len(kept), dropped, no_ref)
    logger.info("by round: %s", dict(sorted(by_round.items())))
    logger.info("by domain: %s", dict(sorted(by_domain.items())))
    logger.info("-> %s", cfg.out_path)


if __name__ == "__main__":
    main()
