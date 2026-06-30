"""OSWorld task generator v2 (forward / context-aware proposer, PAE-style).

Generate NEW file-free OSWorld task drafts across several apps via a GPT-5.5
proposer. Tasks feed *rollout* (each rolled out multiple times, success+failure
kept), so ~1.5k distinct tasks -> ~6k trajectories. Output = OSWorld task JSON
*without* the evaluator field (success verified separately by an LLM/VLM judge).

Two dedup gates:
  * leakage  vs official tasks   -> strict threshold (anti-contamination)
  * repeat   vs already-generated -> loose threshold (keep parameterized variants)

Proposer endpoint (OpenAI-compatible) from env:
  OPENAI_BASE_URL, OPENAI_API_KEY, OSWORLD_PROPOSER_MODEL (default 'gpt-5.5').

Usage:
  python osworld_task_gen.py --apps chrome,vlc,vs_code,os --target-total 1500 \
      --osworld-root /data/hwt/OSWorld --out task_drafts.json
"""

from __future__ import annotations

import argparse
import glob
import json
import logging
import math
import os
import re
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Set

import requests

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

LEAK_THRESHOLD = 0.62   # vs official tasks: strict, anti-leakage.
ALLOWED_DIFFICULTY = {"easy", "medium", "hard"}


@dataclass(frozen=True)
class AppSpec:
    """Per-app generation spec. `mode` = 'settings' (fixed boilerplate, no setup)
    or 'fileops' (proposer also emits setup_shell -> execute steps).
    `repeat_threshold` = dedup-vs-generated cutoff: strict for finite settings
    spaces, loose for parameterized fileops variants."""
    examples_dir: str            # OSWorld folder name (note: vscode -> 'vs_code')
    mode: str
    boilerplate: List[Dict[str, Any]]
    focus_areas: List[str]
    repeat_threshold: float


APP_SPECS: Dict[str, AppSpec] = {
    "chrome": AppSpec(
        examples_dir="chrome", mode="settings",
        boilerplate=[
            {"type": "launch", "parameters": {"command": ["google-chrome", "--remote-debugging-port=1337"]}},
            {"type": "launch", "parameters": {"command": ["socat", "tcp-listen:9222,fork", "tcp:localhost:1337"]}},
        ],
        focus_areas=["privacy and cookies", "downloads behavior", "appearance and zoom",
                     "autofill (addresses/payments)", "site settings (javascript/popups)",
                     "on-startup and on-exit", "accessibility and fonts", "languages and translate",
                     "safe browsing and security", "performance and preload"],
        repeat_threshold=0.72,
    ),
    "vlc": AppSpec(
        examples_dir="vlc", mode="settings",
        boilerplate=[{"type": "launch", "parameters": {"command": "VLC_VERBOSE=-1 vlc --no-audio --no-video-title-show", "shell": True}}],
        focus_areas=["interface and view", "audio preferences", "video preferences",
                     "subtitles and OSD", "playback and hotkeys", "playlist behavior", "metadata display"],
        repeat_threshold=0.72,
    ),
    "vs_code": AppSpec(
        examples_dir="vs_code", mode="settings",
        boilerplate=[
            {"type": "launch", "parameters": {"command": ["code"]}},
            {"type": "activate_window", "parameters": {"window_name": "Visual Studio Code"}},
        ],
        focus_areas=["editor settings", "appearance and theme", "files and autosave",
                     "integrated terminal", "keyboard shortcuts", "formatting and whitespace"],
        repeat_threshold=0.72,
    ),
    "os": AppSpec(
        examples_dir="os", mode="fileops",
        boilerplate=[],
        focus_areas=["create files and directories", "copy and move", "batch rename",
                     "find by pattern", "permissions and ownership", "archive and extract",
                     "text processing on files", "disk usage and cleanup"],
        repeat_threshold=0.90,
    ),
}


def load_existing_instructions(osworld_root: str, examples_dir: str) -> List[str]:
    pattern = os.path.join(osworld_root, "evaluation_examples", "examples", examples_dir, "*.json")
    out: List[str] = []
    for f in glob.glob(pattern):
        try:
            with open(f, encoding="utf-8") as fh:
                out.append(json.load(fh)["instruction"])
        except (KeyError, json.JSONDecodeError, OSError) as e:
            logger.warning("skip %s: %s", f, e)
    return out


def _normalize(text: str) -> Set[str]:
    return set(re.sub(r"[^a-z0-9 ]", " ", text.lower()).split())


def _jaccard(a: Set[str], b: Set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def is_leak(words: Set[str], official_tokens: List[Set[str]]) -> bool:
    return any(_jaccard(words, t) >= LEAK_THRESHOLD for t in official_tokens)


def is_repeat(words: Set[str], kept_tokens: List[Set[str]], threshold: float) -> bool:
    return any(_jaccard(words, t) >= threshold for t in kept_tokens)


def build_messages(app: str, spec: AppSpec, existing: List[str], n: int, focus: str) -> List[Dict[str, str]]:
    few_shot = "\n".join(f"- {s}" for s in existing[:10])
    avoid = "\n".join(f"- {s}" for s in existing)
    if spec.mode == "settings":
        rules = (
            "Each task toggles/changes an app SETTING and needs NO input file. "
            "Keys per element: instruction (str), success_nl (str), est_steps (int), "
            "difficulty (easy/medium/hard)."
        )
    else:  # fileops
        rules = (
            "Each task operates on files/dirs and is fully self-contained: provide a "
            "setup_shell (list of shell commands using mkdir/printf/echo/touch only, NO "
            "external downloads) that creates the initial files the task acts on. "
            "Use ONLY paths under ~/Desktop or ~/Documents (the VM user's home is "
            "/home/user); never use absolute paths like /home/oai or /tmp. "
            "Keys per element: instruction (str), success_nl (str), setup_shell (list[str]), "
            "est_steps (int), difficulty (easy/medium/hard)."
        )
    system = (
        f"You are a task proposer for OSWorld (real Ubuntu desktop GUI benchmark), app '{app}'. "
        f"Generate NEW tasks focused on: {focus}. Each must be achievable via the real GUI on a "
        f"default install, a single clear goal, 2-6 steps, and NOT a paraphrase of any avoid-list "
        f"item. {rules} Return ONLY a JSON array."
    )
    user = (
        f"Style reference (match tone, do not copy):\n{few_shot}\n\n"
        f"AVOID-LIST (never duplicate/paraphrase):\n{avoid}\n\n"
        f"Propose {n} new diverse '{app}' tasks about '{focus}' as a JSON array."
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def call_proposer(messages: List[Dict[str, str]], model: str, retries: int = 5) -> str:
    """Call the proposer with retry + capped backoff to ride out gateway blips (524/5xx)."""
    base_url = os.environ["OPENAI_BASE_URL"].rstrip("/")
    api_key = os.environ["OPENAI_API_KEY"]
    last_err: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            resp = requests.post(
                f"{base_url}/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={"model": model, "messages": messages, "temperature": 1.0},
                timeout=180,
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]
        except (requests.RequestException, KeyError, IndexError, ValueError) as e:
            last_err = e
            logger.warning("proposer attempt %d/%d failed: %s", attempt, retries, e)
            if attempt < retries:
                time.sleep(min(5 * attempt, 30))
    raise RuntimeError(f"proposer failed after {retries} attempts: {last_err}")


def parse_tasks(raw: str) -> List[Dict[str, Any]]:
    text = re.sub(r"```(?:json)?", "", raw).strip()
    try:
        data: Any = json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("["), text.rfind("]")
        if start == -1 or end <= start:
            return []
        try:
            data = json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            return []
    return [d for d in data if isinstance(d, dict)] if isinstance(data, list) else []


def to_osworld_task(draft: Dict[str, Any], app: str, spec: AppSpec) -> Dict[str, Any]:
    try:
        est_steps = int(draft.get("est_steps", 0))
    except (TypeError, ValueError):
        est_steps = 0
    difficulty = draft.get("difficulty", "medium")
    if difficulty not in ALLOWED_DIFFICULTY:
        difficulty = "medium"
    setup_steps: List[Dict[str, Any]] = []
    if spec.mode == "fileops":
        setup_steps = [
            {"type": "execute", "parameters": {"command": cmd, "shell": True}}
            for cmd in (draft.get("setup_shell") or [])
            if isinstance(cmd, str) and cmd.strip()
        ]
    # setup runs first (create files), then the app boilerplate; preserve GPT's order.
    config = setup_steps + [dict(step) for step in spec.boilerplate]
    return {
        "id": f"gen-{app}-{uuid.uuid4().hex[:8]}",
        "snapshot": spec.examples_dir,
        "instruction": str(draft.get("instruction", "")).strip(),
        "source": "synthetic-gpt-proposer",
        "config": config,
        "related_apps": [app],
        "success_nl": str(draft.get("success_nl", "")).strip(),
        "est_steps": est_steps,
        "difficulty": difficulty,
        "needs_file": False,
    }


def generate_for_app(app: str, spec: AppSpec, target: int, batch: int, model: str,
                     osworld_root: str, official_tokens: List[Set[str]]) -> List[Dict[str, Any]]:
    existing = load_existing_instructions(osworld_root, spec.examples_dir)
    kept: List[Dict[str, Any]] = []
    kept_tokens: List[Set[str]] = []
    max_batches = math.ceil(target / batch) * 3 + 5
    dry = 0   # consecutive batches adding ~nothing -> task space saturated.
    fails = 0  # consecutive proposer failures -> give up (transient outage).
    for b in range(max_batches):
        if len(kept) >= target or dry >= 3:
            break
        focus = spec.focus_areas[b % len(spec.focus_areas)]
        try:
            raw = call_proposer(build_messages(app, spec, existing, batch, focus), model)
        except RuntimeError as e:
            fails += 1
            logger.warning("[%s] batch %d skipped (%d consecutive fails): %s", app, b + 1, fails, e)
            if fails >= 4:
                logger.error("[%s] giving up after %d consecutive failures, keeping %d tasks", app, fails, len(kept))
                break
            continue
        fails = 0
        added = 0
        for d in parse_tasks(raw):
            instruction = str(d.get("instruction", "")).strip()
            if not instruction:
                continue
            words = _normalize(instruction)
            if is_leak(words, official_tokens) or is_repeat(words, kept_tokens, spec.repeat_threshold):
                continue
            kept_tokens.append(words)
            kept.append(to_osworld_task(d, app, spec))
            added += 1
        dry = dry + 1 if added <= 1 else 0
        logger.info("[%s] batch %d/%d focus=%s +%d -> kept %d/%d (dry=%d)",
                    app, b + 1, max_batches, focus, added, len(kept), target, dry)
    if dry >= 3:
        logger.info("[%s] saturated at %d tasks (space exhausted before target %d)", app, len(kept), target)
    return kept[:target]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apps", default="chrome,vlc,vs_code,os")
    parser.add_argument("--target-total", type=int, default=1500)
    parser.add_argument("--batch", type=int, default=25)
    parser.add_argument("--osworld-root", default="/data/hwt/OSWorld")
    parser.add_argument("--out", default="task_drafts.json")
    args = parser.parse_args()

    apps = [a.strip() for a in args.apps.split(",") if a.strip()]
    unknown = [a for a in apps if a not in APP_SPECS]
    if unknown:
        parser.error(f"unknown apps: {unknown}; choose from {sorted(APP_SPECS)}")
    if args.target_total < len(apps) or args.batch < 1:
        parser.error("--target-total must be >= #apps and --batch >= 1")
    if not os.environ.get("OPENAI_BASE_URL") or not os.environ.get("OPENAI_API_KEY"):
        raise SystemExit("set OPENAI_BASE_URL and OPENAI_API_KEY in env before running")

    model = os.environ.get("OSWORLD_PROPOSER_MODEL", "gpt-5.5")
    per_app = math.ceil(args.target_total / len(apps))
    all_tasks: List[Dict[str, Any]] = []
    for app in apps:
        spec = APP_SPECS[app]
        official_tokens = [_normalize(s) for s in load_existing_instructions(args.osworld_root, spec.examples_dir)]
        tasks = generate_for_app(app, spec, per_app, args.batch, model, args.osworld_root, official_tokens)
        all_tasks.extend(tasks)
        # Checkpoint after EVERY app so a later failure can't discard earlier work.
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump(all_tasks, fh, ensure_ascii=False, indent=2)
        logger.info("== %s done: %d tasks (checkpointed %d total -> %s) ==", app, len(tasks), len(all_tasks), args.out)

    logger.info("wrote %d tasks across %s -> %s", len(all_tasks), apps, args.out)
    logger.info("NEXT: smoke-run each in OSWorld (drop setup failures), then rollout N times/task.")


if __name__ == "__main__":
    main()
