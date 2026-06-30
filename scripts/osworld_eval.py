"""Post-rollout evaluation: rule prefilter + one VLM 3-way verdict.

Only judge against references whose OWN exploration succeeded (end_reason ==
"done"); a non-done reference is not a valid success standard.

Pipeline (only these steps; skill/training are later):
  ① rule prefilter (no VLM): drop corrupted / obvious external failures
       - corrupted: traj.jsonl unreadable/empty, no screenshots, no parseable action
       - obvious external failure: final frame blank (all black/white)
  ② reference filter: drop episodes with no matching done-reference (no_done_ref).
  ③ VLM 3-way verdict (one call per episode): the judge sees the FULL action text
     plus the LAST few frames (outcome needs the final states; the action text
     conveys the process), then classifies: success / capability_fail / env_fail
       - env_fail  -> dropped (this is the "clean out external failure" part)
       - success / capability_fail -> kept (with "verdict + what went wrong")

Endpoint from env (same as explorer/hindsight):
  OPENAI_BASE_URL, OPENAI_API_KEY, OSWORLD_PROPOSER_MODEL (default 'gpt-5.5').

Run:
  python osworld_eval.py --rounds-glob 'rollout_8b/r[0-5]' \
      --tasks-glob 'explore_0629/*_peeu_tasks.jsonl' \
      --out judged.jsonl --dropped dropped.jsonl
"""

from __future__ import annotations

import argparse
import base64
import glob
import hashlib
import json
import logging
import os
import re
import time
from collections import Counter
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import requests

try:
    from PIL import Image
    _HAS_PIL = True
except ImportError:
    _HAS_PIL = False

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

_COORD_RE = re.compile(r"pyautogui\.[A-Za-z]+\([^)]*\d")
_SPECIAL = ("DONE", "WAIT", "FAIL")
_STEP_RE = re.compile(r"step_(\d+)")


@dataclass(frozen=True)
class EvalConfig:
    rounds_glob: str
    tasks_glob: str
    out_path: str
    dropped_path: str
    model: str
    temperature: float
    max_frames: int
    limit: int
    per_app: int
    apps: Optional[List[str]]


# ---------------- shared helpers ----------------

def is_valid_action(action: str) -> bool:
    a = (action or "").strip()
    if not a:
        return False
    if any(s in a for s in _SPECIAL):
        return True
    return bool(_COORD_RE.search(a))


def load_steps(traj_path: str) -> Optional[List[Dict[str, Any]]]:
    if not os.path.exists(traj_path):
        return None
    steps: List[Dict[str, Any]] = []
    with open(traj_path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                steps.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return steps or None


def list_frames(ep_dir: str) -> List[str]:
    pngs = [p for p in os.listdir(ep_dir) if p.startswith("step_") and p.endswith(".png")]
    pngs.sort(key=lambda n: int(m.group(1)) if (m := _STEP_RE.search(n)) else -1)
    return pngs


def is_blank(path: str) -> bool:
    """True if the frame is all black/white (obvious external failure). Needs PIL."""
    if not _HAS_PIL:
        return False
    try:
        im = Image.open(path).convert("L").resize((32, 32))
        px = list(im.getdata())
        mean = sum(px) / len(px)
        return mean < 8 or mean > 248
    except Exception:  # noqa: BLE001
        return False


def round_of(ep_dir: str) -> str:
    m = re.search(r"/(r\d)/", ep_dir + "/")
    return m.group(1) if m else "?"


def build_ref_map(tasks_glob: str) -> Dict[str, Dict[str, Any]]:
    """Map md5(task)[:10] -> reference, keeping ONLY references whose own
    exploration succeeded (end_reason == "done"). A non-done reference is not a
    valid success standard, so episodes pointing at it get dropped downstream."""
    ref: Dict[str, Dict[str, Any]] = {}
    n_total = 0
    skipped: Counter = Counter()
    for f in sorted(glob.glob(tasks_glob)):
        with open(f, encoding="utf-8") as fh:
            for line in fh:
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
                n_total += 1
                end_reason = t.get("end_reason")
                if end_reason != "done":
                    skipped[end_reason or "<none>"] += 1
                    continue
                h = hashlib.md5(task.encode()).hexdigest()[:10]
                ref[h] = {
                    "instruction": task,
                    "constraints": t.get("constraints") or [],
                    "plan": t.get("plan") or [],
                    "experiences": t.get("experiences") or [],
                    "app": t.get("app"),
                    "end_reason": end_reason,
                }
    logger.info("references: %d total, %d done kept, skipped non-done: %s",
                n_total, len(ref), dict(skipped))
    return ref


# ---------------- ① rule prefilter ----------------

def prefilter(ep_dir: str) -> Tuple[bool, str]:
    """Return (keep, reason). keep=False means drop with the given reason."""
    steps = load_steps(os.path.join(ep_dir, "traj.jsonl"))
    if steps is None:
        return False, "corrupt:no_traj"
    frames = list_frames(ep_dir)
    if not frames:
        return False, "corrupt:no_frames"
    actions = [(s.get("action") or "").strip() for s in steps]
    if not any(is_valid_action(a) for a in actions):
        return False, "corrupt:no_valid_action"
    if is_blank(os.path.join(ep_dir, frames[-1])):
        return False, "env:blank_final_frame"
    return True, ""


# ---------------- ② VLM 3-way verdict ----------------

SYSTEM_PROMPT = (
    "You evaluate a GUI agent's run on an Ubuntu desktop. You get the agent's ACTION "
    "SEQUENCE and SCREENSHOTS (labeled by step), plus a REFERENCE describing the intended "
    "task and a known-good run.\n\n"
    "Do it in three parts:\n"
    "1. DESCRIBE objectively what the run did (key actions, how the screen changed, final "
    "state). Judge only from what is visible; do not assume.\n"
    "2. CLASSIFY into exactly one label:\n"
    "   - success: the task was accomplished (matches the reference's end goal).\n"
    "   - capability_fail: the app/environment worked fine, but the AGENT failed (misclick, "
    "wrong/missing steps, got stuck, never finished). The agent crashing the app by its own "
    "wrong actions counts as capability_fail.\n"
    "   - env_fail: the environment was broken so the agent never had a fair chance — app "
    "never opened, blank/frozen screen, seeded files/setup missing, network down. NOT the "
    "agent's fault.\n"
    "3. Say in one sentence what was achieved / what went wrong (this feeds skill summary).\n\n"
    "Output STRICT JSON only:\n"
    '{"description": "<objective, what the run did>", "label": "success|capability_fail|env_fail", '
    '"reason": "<one sentence: achieved what / wrong where>"}'
)


def _img_block(png_bytes: bytes) -> Dict[str, Any]:
    uri = "data:image/png;base64," + base64.b64encode(png_bytes).decode("utf-8")
    return {"type": "image_url", "image_url": {"url": uri, "detail": "high"}}


def call_gpt(messages: List[Dict[str, Any]], cfg: EvalConfig, retries: int = 5) -> str:
    base_url = os.environ["OPENAI_BASE_URL"].rstrip("/")
    api_key = os.environ["OPENAI_API_KEY"]
    last_err: Optional[Exception] = None
    for attempt in range(1, retries + 1):
        try:
            resp = requests.post(
                f"{base_url}/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={"model": cfg.model, "messages": messages,
                      "temperature": cfg.temperature, "max_tokens": 1200},
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


def select_frames(frames: List[str], max_frames: int) -> List[str]:
    """Outcome judging mainly needs the final states, so keep the LAST
    `max_frames` frames; the full action text conveys the process."""
    if max_frames <= 0 or len(frames) <= max_frames:
        return frames
    return frames[-max_frames:]


def fmt_experiences(exps: List[Any]) -> str:
    lines: List[str] = []
    for e in exps:
        if isinstance(e, dict):
            lines.append(f"- {e.get('state_before','')} --[{e.get('action','')}]--> {e.get('state_after','')}")
        else:
            lines.append(f"- {e}")
    return "\n".join(lines) or "(none)"


def build_user(ref: Dict[str, Any], actions: List[str], ep_dir: str, frames: List[str]) -> List[Dict[str, Any]]:
    constraints = "\n".join(f"{i+1}. {c}" for i, c in enumerate(ref.get("constraints", []))) or "(none)"
    plan = "\n".join(f"- {p}" for p in ref.get("plan", [])) or "(none)"
    exps = fmt_experiences(ref.get("experiences", []))
    act_txt = "\n".join(f"{i+1}. {a}" for i, a in enumerate(actions)) or "(none)"
    text = (
        f"REFERENCE task:\n{ref.get('instruction','(unknown)')}\n\n"
        f"Reference constraints (what 'done' requires):\n{constraints}\n\n"
        f"Reference plan:\n{plan}\n\n"
        f"Reference experiences (real state transitions of a good run):\n{exps}\n\n"
        f"AGENT action sequence ({len(actions)} steps):\n{act_txt}\n\n"
        f"Screenshots below are the agent's run ({len(frames)} frames shown), in order."
    )
    content: List[Dict[str, Any]] = [{"type": "text", "text": text}]
    for fr in frames:
        step = _STEP_RE.search(fr)
        content.append({"type": "text", "text": f"[frame at step {step.group(1) if step else '?'}]"})
        with open(os.path.join(ep_dir, fr), "rb") as fh:
            content.append(_img_block(fh.read()))
    return content


def parse_verdict(raw: str) -> Dict[str, Any]:
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```[a-zA-Z]*\n?", "", cleaned).rstrip("`").strip()
    start = cleaned.find("{")
    if start == -1:
        raise ValueError("no JSON object in output")
    obj, _ = json.JSONDecoder().raw_decode(cleaned[start:])
    return obj


def vlm_verdict(ep_dir: str, ref: Dict[str, Any], cfg: EvalConfig) -> Dict[str, Any]:
    steps = load_steps(os.path.join(ep_dir, "traj.jsonl")) or []
    actions = [(s.get("action") or "").strip() for s in steps]
    frames = select_frames(list_frames(ep_dir), cfg.max_frames)
    content = build_user(ref, actions, ep_dir, frames)
    messages = [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": content}]
    raw = call_gpt(messages, cfg)
    v = parse_verdict(raw)
    v["n_frames_shown"] = len(frames)
    return v


# ---------------- driver ----------------

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rounds-glob", default="rollout_8b/r[0-5]")
    ap.add_argument("--tasks-glob", default="explore_0629/*_peeu_tasks.jsonl")
    ap.add_argument("--out", default="judged.jsonl")
    ap.add_argument("--dropped", default="dropped.jsonl")
    ap.add_argument("--model", default=os.environ.get("OSWORLD_PROPOSER_MODEL", "gpt-5.5"))
    ap.add_argument("--temperature", type=float, default=0.0)
    ap.add_argument("--max-frames", type=int, default=5,
                    help="number of trailing frames shown to the judge (last N)")
    ap.add_argument("--limit", type=int, default=0, help="0 = all")
    ap.add_argument("--per-app", type=int, default=0,
                    help="0 = no cap; else judge at most N episodes per app (sampling)")
    ap.add_argument("--apps", default=None)
    ap.add_argument("--resume", action="store_true",
                    help="skip dirs already in out/dropped and append (for restart)")
    args = ap.parse_args()

    cfg = EvalConfig(
        rounds_glob=args.rounds_glob, tasks_glob=args.tasks_glob, out_path=args.out,
        dropped_path=args.dropped, model=args.model, temperature=args.temperature,
        max_frames=args.max_frames, limit=args.limit, per_app=args.per_app,
        apps=args.apps.split(",") if args.apps else None,
    )
    ref_map = build_ref_map(cfg.tasks_glob)
    logger.info("reference map: %d tasks | PIL=%s", len(ref_map), _HAS_PIL)

    dirs = sorted({os.path.dirname(p) for p in glob.glob(f"{cfg.rounds_glob}/**/traj.jsonl", recursive=True)})
    logger.info("episode dirs: %d", len(dirs))

    seen: set = set()
    mode = "w"
    if args.resume:
        for p in (cfg.out_path, cfg.dropped_path):
            if not os.path.exists(p):
                continue
            with open(p, encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        seen.add(json.loads(line).get("dir"))
                    except json.JSONDecodeError:
                        continue
        mode = "a"
        logger.info("resume: %d already-processed dirs skipped", len(seen))

    pre_drop: Counter = Counter()
    labels: Counter = Counter()
    app_count: Counter = Counter()
    n_judged = 0
    fout = open(cfg.out_path, mode, encoding="utf-8", buffering=1)
    fdrop = open(cfg.dropped_path, mode, encoding="utf-8", buffering=1)
    try:
        for d in dirs:
            if d in seen:
                continue
            tid = os.path.basename(d)
            ref = ref_map.get(tid.split("-")[-1])
            if cfg.apps and (ref is None or ref.get("app") not in cfg.apps):
                continue
            keep, reason = prefilter(d)
            if not keep:
                pre_drop[reason] += 1
                fdrop.write(json.dumps({"task_id": tid, "dir": d, "stage": "prefilter", "reason": reason}) + "\n")
                continue
            if ref is None:
                pre_drop["no_done_ref"] += 1
                fdrop.write(json.dumps({"task_id": tid, "dir": d, "stage": "ref_filter", "reason": "no_done_ref"}) + "\n")
                continue
            app = ref.get("app") or "?"
            if cfg.per_app and app_count[app] >= cfg.per_app:
                continue
            try:
                v = vlm_verdict(d, ref, cfg)
            except Exception as e:  # noqa: BLE001
                v = {"label": "error", "reason": f"judge_fail: {e}"}
            label = v.get("label", "error")
            labels[label] += 1
            app_count[app] += 1
            row = {"task_id": tid, "round": round_of(d), "domain": d.split("/qwen3vl8b/")[-1].split("/")[0],
                   "dir": d, **v}
            if label == "env_fail":
                fdrop.write(json.dumps({**row, "stage": "vlm"}, ensure_ascii=False) + "\n")
            else:
                fout.write(json.dumps(row, ensure_ascii=False) + "\n")
                n_judged += 1
            if cfg.limit and (n_judged + sum(pre_drop.values())) >= cfg.limit:
                break
    finally:
        fout.close()
        fdrop.close()

    logger.info("prefilter dropped: %s", dict(pre_drop))
    logger.info("vlm labels: %s", dict(labels))
    logger.info("kept (success+capability_fail): %d -> %s", n_judged, cfg.out_path)
    logger.info("dropped -> %s", cfg.dropped_path)


if __name__ == "__main__":
    main()
