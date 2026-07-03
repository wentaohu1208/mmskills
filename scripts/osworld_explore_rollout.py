"""Self-exploration -> tagged trajectory library on OSWorld (explore stage only).

Let GPT-5.5 EXPLORE an Ubuntu app and DISCOVER its own tasks, then keep every rollout labelled by
what it ACTUALLY accomplished -- so each trajectory is a correct demo of its own (reverse-derived)
task BY CONSTRUCTION. No success verifier: verification collapses to a cheap "did something coherent
happen?" gate. Design: doc/explore_rollout_design.md.

Per episode (one exploration = one trajectory):
  (1) SEED    reset the VM, upload a seed file from the pool, open the app on it (varied seeds -> varied tasks)
  (2) GOAL    GPT-5.5 sees the first screen -> proposes ONE worthwhile coarse goal (a MOTIVATOR, not a
              success criterion)
  (3) ROLLOUT GPT-5.5 drives pyautogui toward the goal; record per step screenshot + action + thinking
  (4) GATE    a single MLLM judge decides coherence by a POSITIVE, domain-general criterion -- did the run
              cause a real, PERSISTENT change to content/structure/config? -- NOT a success judgement
  (5) LABEL   (coherent only) GPT-5.5 from first+last screen + actions -> the task actually accomplished
  (6) STORE   keep ALL episodes tagged (coherent + not); layout matches cua_gym_rollout / osworld_eval

Skill synthesis (enrich/distill, clustering, N->1 induction) is a SEPARATE downstream stage, NOT here.

Endpoint (OpenAI-compatible, vision) from env: OPENAI_BASE_URL, OPENAI_API_KEY, OSWORLD_PROPOSER_MODEL.

Run (needs a live OSWorld VM):
  python osworld_explore_rollout.py --app libreoffice_calc --seed-pool seeds/calc \
      --n-episodes 20 --max-steps 20 --provider docker --out-dir explore_calc
"""

from __future__ import annotations

import argparse
import base64
import glob
import json
import logging
import os
import re
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set, Tuple

import requests

from desktop_env.desktop_env import DesktopEnv

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

ACTION_RE = re.compile(r"pyautogui\.[A-Za-z]+\([^\n;]*\)")
_DANGER = ("os.", "import", "subprocess", "exec", "eval", "__")
# per app: which seed file extensions to use (filters out stray cache files) + how to open a seed.
#   open="office" -> OSWorld `open` (default app by extension, waits for load)
#   open="gimp"   -> launch gimp on the image
#   open="vscode" -> reset VS Code session (single-instance leaks state), then open the file in a trusted window
_APP_SPEC: Dict[str, Dict[str, Any]] = {
    "libreoffice_calc":    {"exts": (".xlsx", ".xls", ".ods", ".csv"), "open": "office", "launch": ["libreoffice", "--calc"]},
    "libreoffice_writer":  {"exts": (".docx", ".doc", ".odt", ".rtf"), "open": "office", "launch": ["libreoffice", "--writer"]},
    "libreoffice_impress": {"exts": (".pptx", ".ppt", ".odp"), "open": "office", "launch": ["libreoffice", "--impress"]},
    "gimp":                {"exts": (".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".gif", ".webp", ".xcf"), "open": "gimp"},
    "vs_code":             {"exts": (".py", ".txt", ".md", ".js", ".ts", ".html", ".css", ".json"), "open": "vscode"},
}


@dataclass(frozen=True)
class ExploreConfig:
    app: str
    seed_pool: str
    n_episodes: int
    max_steps: int
    screen_w: int
    screen_h: int
    out_dir: str
    model: str
    temperature: float


# ---------- GPT-5.5 (vision) ----------

def _img_block(png_bytes: bytes) -> Dict[str, Any]:
    uri = "data:image/png;base64," + base64.b64encode(png_bytes).decode("utf-8")
    return {"type": "image_url", "image_url": {"url": uri}}


def call_gpt(messages: List[Dict[str, Any]], cfg: ExploreConfig, retries: int = 5) -> str:
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


def _first_json(raw: str) -> Optional[Any]:
    """Parse the first JSON object/array in a model reply (ignores prose / code fences)."""
    cleaned = re.sub(r"```(?:json)?", "", raw)
    for s in (i for i, c in enumerate(cleaned) if c in "{["):
        try:
            obj, _ = json.JSONDecoder().raw_decode(cleaned[s:])
            if isinstance(obj, list) and len(obj) == 1 and isinstance(obj[0], dict):
                return obj[0]  # unwrap a single-object-in-list reply
            return obj
        except json.JSONDecodeError:
            continue
    return None


def _truthy(v: Any) -> bool:
    """A model may return a JSON bool OR the string 'true'/'false'; coerce safely (string 'false' -> False)."""
    if isinstance(v, bool):
        return v
    return str(v).strip().lower() in ("true", "yes", "1")


# ---------- (3) rollout action ----------

def valid_action(a: str) -> bool:
    """Gate an LLM action: a single bare pyautogui.<fn>(...) call, or DONE."""
    a = a.strip()
    if a.upper() == "DONE":
        return True
    if not a.startswith("pyautogui.") or ";" in a or "\n" in a:
        return False
    head = a.split("(", 1)[0]  # call target only -- never the typed args, e.g. write('important')
    if any(bad in head for bad in _DANGER):
        return False
    return bool(re.fullmatch(r"pyautogui\.[A-Za-z]+\(.*\)", a))


def next_action(goal: str, app: str, png: bytes, history: List[str], cfg: ExploreConfig) -> Tuple[str, str]:
    """One GPT-5.5 turn toward the goal -> (thought, action). Action = ONE absolute-pixel pyautogui, or DONE."""
    system = (
        f"You are exploring the Ubuntu app '{app}' (screen {cfg.screen_w}x{cfg.screen_h}) to accomplish a GOAL. "
        "Each turn, given the current screenshot, output ONE JSON {\"thought\": \"...\", \"action\": \"...\"} where "
        "action is a SINGLE pyautogui command using ABSOLUTE pixel coordinates (e.g. "
        "\"pyautogui.click(960, 540)\", \"pyautogui.write('hello')\", \"pyautogui.hotkey('ctrl','s')\"), or \"DONE\" "
        "when the goal is accomplished. If the goal changes a document, SAVE before DONE. Do not repeat a previous action."
    )
    hist = "\n".join(f"{i + 1}. {a}" for i, a in enumerate(history)) or "(none yet)"
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": [
            {"type": "text", "text": f"GOAL: {goal}\nactions so far:\n{hist}\nNext action as JSON:"},
            _img_block(png),
        ]},
    ]
    raw = call_gpt(messages, cfg)
    obj = _first_json(raw)
    if isinstance(obj, dict) and str(obj.get("action", "")).strip():
        return str(obj.get("thought", "")).strip(), str(obj["action"]).strip()
    am = ACTION_RE.search(raw)  # fallback: pull a bare pyautogui call / DONE from the raw text
    return "", (am.group(0) if am else ("DONE" if "DONE" in raw else ""))


# ---------- (2) propose goal ----------

def propose_goal(first_png: bytes, app: str, done_goals: List[str], cfg: ExploreConfig) -> Dict[str, str]:
    recent = "; ".join(done_goals[-15:])
    diversity = (f"\nPick something DIFFERENT from these already-explored goals: {recent}." if recent else "")
    system = (
        f"You see the first screen of the Ubuntu app '{app}'. Propose ONE concrete, worthwhile thing a user "
        "could accomplish here (an exploration goal): it must leave a real, persistent change to the "
        "document/content/settings, use the on-screen material, and be doable via the GUI in about 3-10 steps. "
        "If the screen ALREADY shows a document with content, prefer OPERATING ON that existing content "
        "(sort/filter/format/chart/compute over the data that is there) rather than creating a new file from "
        "scratch. GOOD goals change state meaningfully (enter/transform data, apply formatting, create an object "
        "like a chart/table/shape, configure a setting, run and verify a command). AVOID trivial goals (just "
        "opening/closing a menu, pure navigation, a single click with no effect)." + diversity +
        "\nReturn ONLY JSON: {\"goal\": \"...\", \"category\": \"<short tag, e.g. formatting/chart/formula>\"}."
    )
    obj = _first_json(call_gpt([{"role": "system", "content": system},
                                {"role": "user", "content": [
                                    {"type": "text", "text": f"Propose one goal for '{app}'."},
                                    _img_block(first_png)]}], cfg))
    if isinstance(obj, dict) and str(obj.get("goal", "")).strip():
        return {"goal": str(obj["goal"]).strip(), "category": str(obj.get("category", "")).strip()}
    return {"goal": "", "category": ""}


# ---------- (4) coherence gate ----------

def coherence_judge(first_png: bytes, last_png: bytes, actions: List[str], cfg: ExploreConfig) -> Dict[str, Any]:
    """The sole coherence arbiter. Positive criterion (domain-general): did the run make a PERSISTENT change?"""
    act = "\n".join(f"{i + 1}. {a}" for i, a in enumerate(actions)) or "(none)"
    system = (
        "You see the FIRST and LAST screen of an agent's short run on an Ubuntu app, plus its ACTION sequence. "
        "Judge whether the run is COHERENT by ONE POSITIVE criterion: it caused a REAL, PERSISTENT change to the "
        "document / application -- a change to CONTENT, STRUCTURE, or CONFIGURATION that would remain after "
        "clicking elsewhere (e.g. data entered or transformed, a formula computed, formatting applied, an object "
        "created, a setting changed, a file produced). If the final state shows such a persistent change, "
        "coherent=true; otherwise coherent=false. This is NOT about matching any particular task -- only whether a "
        "real, lasting change was made.\n"
        "Return ONLY JSON: {\"coherent\": true|false, \"reason\": \"<one sentence>\"}."
    )
    obj = _first_json(call_gpt([{"role": "system", "content": system},
                                {"role": "user", "content": [
                                    {"type": "text", "text": f"ACTIONS:\n{act}\n\nFIRST then LAST screen:"},
                                    _img_block(first_png), _img_block(last_png)]}], cfg))
    if isinstance(obj, dict):
        return {"coherent": _truthy(obj.get("coherent")), "reason": str(obj.get("reason", "")).strip()}
    return {"coherent": False, "reason": "judge_unparseable"}


def coherence_gate(steps: List[Dict[str, Any]], first_png: bytes, last_png: bytes,
                   cfg: ExploreConfig) -> Dict[str, Any]:
    """Coherence is decided SOLELY by the judge (persistent-change criterion). Only a 0-action run -- nothing
    to judge -- is short-circuited."""
    if not steps:
        return {"coherent": False, "reason": "no_actions"}
    return coherence_judge(first_png, last_png, [s["action"] for s in steps], cfg)


# ---------- (5) reverse label ----------

def reverse_label(first_png: bytes, last_png: bytes, actions: List[str], goal: str,
                  cfg: ExploreConfig) -> Dict[str, Any]:
    """From first+last screen + actions, describe the task ACTUALLY accomplished (goal is only a hint)."""
    act = "\n".join(f"{i + 1}. {a}" for i, a in enumerate(actions)) or "(none)"
    system = (
        "You are given the FIRST and LAST screen of an agent's run on an Ubuntu app, plus its ACTION sequence. "
        "Write the TASK this run accomplished as ONE concise, high-level instruction a user would give.\n"
        "Phrase it as REQUIREMENTS / constraints -- WHAT the result must satisfy (the goal), NOT how it was done. "
        "INCLUDE the content/structure/values the outcome has (e.g. 'a Net Sales column equal to Sales minus "
        "Returns minus Discounts', 'rows sorted by the June column in descending order'). EXCLUDE all operational "
        "HOW: which app was opened, which menu/tool/button was used, how cells or ranges were selected, "
        "click/type/save mechanics, cell coordinates -- those belong to the STEPS, not the task.\n"
        "Judge ONLY from the visible before->after change and the actions; do not assume more than happened. "
        "Include ONLY requirements the final state ACTUALLY satisfies; OMIT anything left unfinished or abandoned "
        "(do not mention partial/incomplete attempts at all).\n"
        f"(Hint -- the agent aimed for: '{goal}'. Use only as a hint; describe the actual satisfied result.)\n"
        "Return ONLY JSON: {\"achieved_task\": \"<one concise constraint-style instruction>\", "
        "\"faithful\": true|false} (faithful=false if nothing coherent was actually accomplished)."
    )
    obj = _first_json(call_gpt([{"role": "system", "content": system},
                                {"role": "user", "content": [
                                    {"type": "text", "text": f"ACTIONS:\n{act}\n\nFIRST then LAST screen:"},
                                    _img_block(first_png), _img_block(last_png)]}], cfg))
    if isinstance(obj, dict):
        return {"achieved_task": str(obj.get("achieved_task", "")).strip(),
                "faithful": _truthy(obj.get("faithful"))}
    return {"achieved_task": "", "faithful": False}


# ---------- (1) seed + root config ----------

def list_seeds(cfg: ExploreConfig) -> List[str]:
    """Seed-pool files whose extension fits `app` (drops stray cache files); empty -> explore a blank app."""
    if not cfg.seed_pool or not os.path.isdir(cfg.seed_pool):
        return []
    exts = _APP_SPEC.get(cfg.app, {}).get("exts")
    files = [p for p in sorted(glob.glob(os.path.join(cfg.seed_pool, "*"))) if os.path.isfile(p)]
    out = [p for p in files if not exts or p.lower().endswith(exts)]
    if len(out) < len(files):
        logger.info("seed pool: kept %d/%d files matching %s", len(out), len(files), exts)
    return out


def build_root_config(app: str, seed_path: Optional[str]) -> Dict[str, Any]:
    """OSWorld task_config that opens the app on a seed file (or launches it blank); placeholder evaluator.

    Per-app open (see _APP_SPEC): office uses OSWorld's `open` (default app, WAITS for load); gimp/vscode use
    `launch` + a settle `sleep` (fire-and-forget) with vscode's session reset. A missing/blank seed launches
    the app empty.
    """
    spec = _APP_SPEC.get(app, {})
    mode = spec.get("open", "office")
    config: List[Dict[str, Any]] = []
    vm_path: Optional[str] = None
    if seed_path:
        vm_path = f"/home/user/{os.path.basename(seed_path)}"
        config.append({"type": "upload_file", "parameters": {
            "files": [{"local_path": os.path.abspath(seed_path), "path": vm_path}]}})
    if mode == "office":
        if vm_path:
            config.append({"type": "open", "parameters": {"path": vm_path}})
        else:
            config.append({"type": "launch", "parameters": {"command": spec.get("launch", ["libreoffice"])}})
    elif mode == "gimp":
        config.append({"type": "launch", "parameters": {"command": ["gimp"] + ([vm_path] if vm_path else [])}})
        config.append({"type": "sleep", "parameters": {"seconds": 8}})  # gimp cold-start + image load
    elif mode == "vscode":
        # VS Code is single-instance and restores its last session -> state leaks across episodes. Kill it,
        # disable restore, wipe restorable state, then open a fresh trusted window (on the seed if given).
        reset = ("pkill -f /usr/share/code/code; sleep 1; mkdir -p /home/user/.config/Code/User; "
                 "printf '{\\n  \"window.restoreWindows\": \"none\"\\n}\\n' > "
                 "/home/user/.config/Code/User/settings.json; "
                 "rm -rf /home/user/.config/Code/User/workspaceStorage /home/user/.config/Code/Backups")
        launch = ["code", "--disable-workspace-trust", "--new-window"] + ([vm_path] if vm_path else [])
        config.append({"type": "execute", "parameters": {"command": reset, "shell": True}})
        config.append({"type": "launch", "parameters": {"command": launch}})
        config.append({"type": "sleep", "parameters": {"seconds": 5}})  # let the window render before focusing
        config.append({"type": "activate_window", "parameters": {"window_name": "Visual Studio Code"}})
    return {"id": f"explore-{app}", "instruction": f"explore {app}", "snapshot": app,
            "config": config, "related_apps": [app], "evaluator": {"func": "infeasible"}}


# ---------- (6) one episode ----------

def _save_png(path: str, png: bytes) -> None:
    with open(path, "wb") as fh:
        fh.write(png)


def _finish(ep_dir: str, meta: Dict[str, Any], steps: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Persist the episode (traj.jsonl + meta.json) and return meta. EVERY exit path goes through here."""
    meta["n_steps"] = len(steps)
    with open(os.path.join(ep_dir, "traj.jsonl"), "w", encoding="utf-8") as fh:
        for s in steps:
            fh.write(json.dumps(s, ensure_ascii=False) + "\n")
    with open(os.path.join(ep_dir, "meta.json"), "w", encoding="utf-8") as fh:
        json.dump(meta, fh, ensure_ascii=False, indent=2)
    return meta


def run_episode(env: DesktopEnv, seed_path: Optional[str], cfg: ExploreConfig,
                done_goals: List[str], ep_idx: int) -> Dict[str, Any]:
    """One exploration: seed -> goal -> rollout -> gate -> (reverse label). ALWAYS stored + tagged.

    The whole body is wrapped, so a failure at any point still leaves a tagged episode dir on disk
    (keep-ALL-tagged) rather than an untracked partial dir.
    """
    seed_id = os.path.basename(seed_path) if seed_path else "none"
    ep_dir = os.path.join(cfg.out_dir, cfg.app, f"{ep_idx:03d}")
    os.makedirs(ep_dir, exist_ok=True)
    meta: Dict[str, Any] = {"app": cfg.app, "seed_id": seed_id, "goal": "", "category": "",
                            "coherent": False, "coherence_reason": "", "achieved_task": "",
                            "faithful": False, "n_steps": 0, "end_reason": "", "dir": ep_dir}
    steps: List[Dict[str, Any]] = []
    try:
        obs = env.reset(task_config=build_root_config(cfg.app, seed_path))
        first_png = obs.get("screenshot") if obs else None
        if not first_png:
            meta["end_reason"] = meta["coherence_reason"] = "bad_start"
            return _finish(ep_dir, meta, steps)

        goal_obj = propose_goal(first_png, cfg.app, done_goals, cfg)
        meta["goal"], meta["category"] = goal_obj["goal"], goal_obj["category"]
        if not meta["goal"]:
            logger.warning("[ep%d] propose_goal returned empty goal", ep_idx)
            meta["end_reason"] = meta["coherence_reason"] = "no_goal"
            return _finish(ep_dir, meta, steps)
        done_goals.append(meta["goal"])

        history: List[str] = []
        last_png = first_png
        end_reason = "max_steps"
        for t in range(cfg.max_steps):
            if not obs or not obs.get("screenshot"):
                end_reason = "bad_obs"
                break
            png = obs["screenshot"]
            last_png = png
            _save_png(os.path.join(ep_dir, f"step_{t:02d}_before.png"), png)
            thought, action = next_action(meta["goal"], cfg.app, png, history, cfg)
            if not action:
                end_reason = "no_action"
                break
            if action.upper() == "DONE":
                end_reason = "done"
                break
            if not valid_action(action):
                logger.warning("[ep%d] step %d invalid action dropped: %s", ep_idx, t, action[:60])
                end_reason = "bad_action"
                break
            if action in history[-3:]:  # stuck: repeating a recent action
                end_reason = "stuck"
                break
            steps.append({"index": t, "thought": thought, "action": action,
                          "img_before": f"step_{t:02d}_before.png"})
            history.append(action)
            try:
                obs, _, done, _ = env.step(action)
            except Exception as e:  # a bad pyautogui line shouldn't kill the episode  # noqa: BLE001
                logger.warning("[ep%d] step %d action failed: %s", ep_idx, t, e)
                steps[-1]["exec_error"] = str(e)
                end_reason = "exec_error"
                break
            logger.info("[ep%d] step %d: %s", ep_idx, t, action[:60])
            if obs and obs.get("screenshot"):
                last_png = obs["screenshot"]
            if done:
                end_reason = "env_done"
                break
        _save_png(os.path.join(ep_dir, "final.png"), last_png)
        meta["end_reason"] = end_reason

        gate = coherence_gate(steps, first_png, last_png, cfg)
        meta["coherent"], meta["coherence_reason"] = gate["coherent"], gate["reason"]
        if gate["coherent"]:
            rl = reverse_label(first_png, last_png, [s["action"] for s in steps], meta["goal"], cfg)
            meta["achieved_task"], meta["faithful"] = rl["achieved_task"], rl["faithful"]
        return _finish(ep_dir, meta, steps)
    except Exception as e:  # keep-ALL: a failed episode is still stored + tagged  # noqa: BLE001
        logger.error("episode %d failed: %s", ep_idx, e, exc_info=True)
        meta["end_reason"] = meta["coherence_reason"] = "exception"
        meta["error"] = str(e)
        return _finish(ep_dir, meta, steps)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--app", required=True, choices=sorted(_APP_SPEC),
                        help="app_type (must have an open recipe in _APP_SPEC)")
    parser.add_argument("--seed-pool", default="", help="dir of seed files (empty = explore a blank app)")
    parser.add_argument("--n-episodes", type=int, default=20)
    parser.add_argument("--max-steps", type=int, default=20)
    parser.add_argument("--provider", default="docker")
    parser.add_argument("--path-to-vm", default=None)
    parser.add_argument("--screen-width", type=int, default=1920)
    parser.add_argument("--screen-height", type=int, default=1080)
    parser.add_argument("--temperature", type=float, default=1.0)
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--out-dir", default="explore_out")
    parser.add_argument("--resume", action="store_true",
                        help="skip episode indices already tagged in --out-dir (restart a killed batch)")
    args = parser.parse_args()

    if args.n_episodes < 1 or args.max_steps < 1:
        parser.error("--n-episodes and --max-steps must be >= 1")

    cfg = ExploreConfig(app=args.app, seed_pool=args.seed_pool, n_episodes=args.n_episodes,
                        max_steps=args.max_steps,
                        screen_w=args.screen_width, screen_h=args.screen_height, out_dir=args.out_dir,
                        model=os.environ.get("OSWORLD_PROPOSER_MODEL", "gpt-5.5"), temperature=args.temperature)
    seeds = list_seeds(cfg)
    logger.info("app=%s | seeds=%d | episodes=%d | resume=%s", cfg.app, len(seeds), cfg.n_episodes, args.resume)

    done_goals: List[str] = []
    results: List[Dict[str, Any]] = []
    done_idx: Set[int] = set()
    _RETRYABLE = ("exception", "bad_start", "no_goal")  # transient failures -> re-attempt on --resume
    if args.resume:  # reload COMPLETED episodes so we skip them and keep the diversity history
        for m in sorted(glob.glob(os.path.join(cfg.out_dir, cfg.app, "*", "meta.json"))):
            name = os.path.basename(os.path.dirname(m))
            if not (name.isdigit() and 0 <= int(name) < cfg.n_episodes):
                continue  # stale / unrelated dir from an older or different run
            try:
                with open(m, encoding="utf-8") as fh:
                    d = json.load(fh)
            except (OSError, json.JSONDecodeError):
                continue  # unparseable -> redo this episode
            if d.get("end_reason") in _RETRYABLE:
                continue  # transient failure -> redo (its dir is overwritten cleanly)
            results.append(d)
            if d.get("goal"):
                done_goals.append(d["goal"])
            done_idx.add(int(name))
        logger.info("resume: %d completed episodes preloaded; retrying the rest", len(done_idx))

    todo = [i for i in range(cfg.n_episodes) if i not in done_idx]
    if todo and (not os.environ.get("OPENAI_BASE_URL") or not os.environ.get("OPENAI_API_KEY")):
        raise SystemExit("set OPENAI_BASE_URL and OPENAI_API_KEY in env")
    if todo:
        env = DesktopEnv(provider_name=args.provider, path_to_vm=args.path_to_vm, action_space="pyautogui",
                         screen_size=(args.screen_width, args.screen_height), headless=args.headless,
                         os_type="Ubuntu", require_a11y_tree=False)
        try:
            for i in todo:
                seed = seeds[i % len(seeds)] if seeds else None  # cycle the pool -> varied starting states
                try:
                    meta = run_episode(env, seed, cfg, done_goals, i)
                    results.append(meta)
                    logger.info("[ep%d/%d] coherent=%s steps=%d task=%s", i + 1, cfg.n_episodes,
                                meta["coherent"], meta["n_steps"], (meta["achieved_task"] or "-")[:60])
                except Exception as e:  # backstop: run_episode self-persists; catches any _finish failure  # noqa: BLE001
                    logger.error("episode %d failed hard: %s", i, e, exc_info=True)
                    results.append({"app": cfg.app, "seed_id": os.path.basename(seed) if seed else "none",
                                    "goal": "", "category": "", "coherent": False, "coherence_reason": "exception",
                                    "achieved_task": "", "faithful": False, "n_steps": 0,
                                    "end_reason": "exception", "dir": "", "error": str(e)})
        finally:
            env.close()
    else:
        logger.info("nothing to do: all %d episodes already present", cfg.n_episodes)

    os.makedirs(cfg.out_dir, exist_ok=True)
    index = os.path.join(cfg.out_dir, f"{cfg.app}_episodes.jsonl")
    with open(index, "w", encoding="utf-8") as fh:
        for r in results:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    n_coh = sum(1 for r in results if r.get("coherent"))
    logger.info("done: %d episodes | coherent=%d -> %s", len(results), n_coh, index)
    logger.info("NEXT (separate stage): feed coherent episodes' (achieved_task + traj) to traj2skill.")


if __name__ == "__main__":
    main()
