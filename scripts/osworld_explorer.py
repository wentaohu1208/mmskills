"""M2 - PEEU Stage-1 explorer on OSWorld (planning tree exploration, linear cut).

Faithful to PEEU Eq.1-2: propose exploration goals from the app's first screenshot
(M1), then for each goal reset the VM to the shared root and let GPT-5.5 drive
pyautogui exploration for <=N steps, recording the trajectory tau = [(s_t, a_t,
s_{t+1})] with screenshots + a11y trees. Output feeds M3/M4 (state-diff + reverse
task synthesis).

"Tree" is realized as N root-sharing linear trajectories (PEEU's tree shares one
root); each goal resets to root via env.reset(root_config) -> no per-node
snapshots needed (this VM reset per goal is the intended, dominant cost).

Endpoint (OpenAI-compatible, vision) from env:
  OPENAI_BASE_URL, OPENAI_API_KEY, OSWORLD_PROPOSER_MODEL (default 'gpt-5.5').

Run (needs a live OSWorld VM; match your run.py provider/path):
  python osworld_explorer.py --app chrome --provider vmware --path-to-vm <vmx> \
      --n-goals 10 --max-steps 15 --out-dir explore_out
"""

from __future__ import annotations

import argparse
import base64
import json
import logging
import os
import re
import time
import uuid
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import requests

from desktop_env.desktop_env import DesktopEnv

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# Minimal "root" task_config per app = just open the app (no evaluator needed).
ROOT_CONFIG: Dict[str, List[Dict[str, Any]]] = {
    "chrome": [
        {"type": "launch", "parameters": {"command": ["google-chrome", "--remote-debugging-port=1337"]}},
        {"type": "launch", "parameters": {"command": ["socat", "tcp-listen:9222,fork", "tcp:localhost:1337"]}},
    ],
    "vlc": [{"type": "launch", "parameters": {"command": "VLC_VERBOSE=-1 vlc --no-audio --no-video-title-show", "shell": True}}],
    # VS Code is single-instance and restores its last session, so a plain relaunch only re-focuses the
    # previous (dirty) window -> UI state leaks across goals. Kill it, disable session restore, wipe
    # restorable workspace state, then open a fresh trusted window. We deliberately clobber settings.json:
    # the exploration VM ships no user settings worth preserving.
    "vs_code": [
        {"type": "execute", "parameters": {"command": "pkill -f /usr/share/code/code; sleep 1; mkdir -p /home/user/.config/Code/User; printf '{\\n  \"window.restoreWindows\": \"none\"\\n}\\n' > /home/user/.config/Code/User/settings.json; rm -rf /home/user/.config/Code/User/workspaceStorage /home/user/.config/Code/Backups", "shell": True}},
        {"type": "launch", "parameters": {"command": ["code", "--disable-workspace-trust", "--new-window"]}},
        {"type": "activate_window", "parameters": {"window_name": "Visual Studio Code"}},
    ],
    "gimp": [{"type": "launch", "parameters": {"command": ["gimp"]}}],
    "libreoffice_calc": [{"type": "launch", "parameters": {"command": ["libreoffice", "--calc"]}}],
    "libreoffice_writer": [{"type": "launch", "parameters": {"command": ["libreoffice", "--writer"]}}],
    "libreoffice_impress": [{"type": "launch", "parameters": {"command": ["libreoffice", "--impress"]}}],
    "os": [],
    # thunderbird: seed a pre-configured profile (account + emails), copied from official tasks.
    "thunderbird": [
        {"type": "download", "parameters": {"files": [{
            "url": "https://huggingface.co/datasets/xlangai/ubuntu_osworld_file_cache/resolve/main/thunderbird/dd84e895-72fd-4023-a336-97689ded257c/thunderbird-profile.tar.gz",
            "path": "/home/user/thunderbird-profile.tar.gz"}]}},
        {"type": "execute", "parameters": {"command": ["tar", "-xzv", "--recursive-unlink", "-f", "/home/user/thunderbird-profile.tar.gz", "-C", "/home/user/"]}},
        # tarball has profiles.ini + installs.ini, but installs.ini keys on the original install
        # hash and won't match docker's Thunderbird -> wizard. Remove stale locks and launch with
        # the profile path explicitly, bypassing profiles.ini/installs.ini selection.
        {"type": "execute", "parameters": {"command": "rm -f '/home/user/.thunderbird/t5q2a5hp.default-release/lock' '/home/user/.thunderbird/t5q2a5hp.default-release/.parentlock'", "shell": True}},
        {"type": "launch", "parameters": {"command": ["/usr/bin/thunderbird", "--profile", "/home/user/.thunderbird/t5q2a5hp.default-release"]}},
    ],
    # multi_apps: seed files AND open one in Calc so the explorer starts with visible material,
    # then must bring in/switch to other apps (cross-application workflows). Needs a long budget.
    "multi_apps": [
        {"type": "execute", "parameters": {"command": "mkdir -p /home/user/Desktop/work && printf 'Product,Q1,Q2\\nAlpha,100,120\\nBeta,90,150\\nGamma,70,80\\n' > /home/user/Desktop/work/sales.csv && printf 'Quarterly Report\\n\\nSummary:\\n' > /home/user/Desktop/work/report.txt", "shell": True}},
        {"type": "launch", "parameters": {"command": ["libreoffice", "--calc", "/home/user/Desktop/work/sales.csv"]}},
    ],
}

# Extra per-app context injected into prompts (tells the model about seeded state it can't infer).
CONTEXT_HINT: Dict[str, str] = {
    "multi_apps": ("Seeded on the Desktop: /home/user/Desktop/work/sales.csv (a 3-row sales table, "
                   "already open in LibreOffice Calc) and /home/user/Desktop/work/report.txt (a report "
                   "draft). Goals should COMBINE content across apps, e.g. chart the sales data and put "
                   "it into the report, or summarize the spreadsheet in Writer."),
}

# Per-app exploration focus areas (drives M1 diversity); falls back to generic if absent.
APP_FOCUS: Dict[str, List[str]] = {
    "libreoffice_calc": ["enter data into cells", "apply a formula", "format cells", "create a chart", "sort/filter a range"],
    "libreoffice_writer": ["type and format text", "apply styles/headings", "insert table or image", "page layout", "find and replace"],
    "libreoffice_impress": ["add a slide", "edit slide text", "apply a layout/theme", "insert shape or image", "slide transitions"],
    "thunderbird": ["read and reply to an email", "organize emails into folders", "search the mailbox",
                    "create a message filter", "compose and format a new email", "manage account/display settings"],
    "multi_apps": ["open sales.csv in LibreOffice Calc and make a chart", "copy data from Calc into the report",
                   "open report.txt in Writer and format it", "create an image in GIMP and insert it into a document",
                   "use the file manager to organize the work folder then open a file"],
}

ACTION_RE = re.compile(r"pyautogui\.[A-Za-z]+\([^\n;]*\)")
_DANGER = ("os.", "import", "subprocess", "exec(", "eval(", "__", "open(")
MAX_A11Y_CHARS = 400_000  # cap raw a11y dump per step.


@dataclass(frozen=True)
class ExploreConfig:
    app: str
    n_goals: int
    max_steps: int
    screen_w: int
    screen_h: int
    out_dir: str
    model: str
    temperature: float = 1.0


def valid_action(a: str) -> bool:
    """Gate an LLM action: only a single bare pyautogui.<fn>(...) call, or DONE."""
    a = a.strip()
    if a.upper() == "DONE":
        return True
    if not a.startswith("pyautogui.") or ";" in a or "\n" in a:
        return False
    if any(bad in a for bad in _DANGER):
        return False
    return bool(re.fullmatch(r"pyautogui\.[A-Za-z]+\(.*\)", a))


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


# ---------- M1: propose goals from first screen ----------

def propose_goals(first_png: bytes, cfg: ExploreConfig) -> List[str]:
    focus = APP_FOCUS.get(cfg.app)
    hint = (" Cover varied areas such as: " + "; ".join(focus) + ".") if focus else ""
    ctx = (" " + CONTEXT_HINT[cfg.app]) if cfg.app in CONTEXT_HINT else ""
    system = (
        f"You look at the first screen of the Ubuntu app '{cfg.app}' and propose {cfg.n_goals} "
        "diverse, concrete things a user could DO here (exploration goals), each achievable via the "
        f"GUI in a few steps.{hint}{ctx} Return ONLY a JSON array of short goal strings."
    )
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": [{"type": "text", "text": f"Propose {cfg.n_goals} goals for '{cfg.app}'."}, _img_block(first_png)]},
    ]
    raw = call_gpt(messages, cfg)
    text = re.sub(r"```(?:json)?", "", raw).strip()
    start, end = text.find("["), text.rfind("]")
    if start == -1 or end <= start:
        return []
    try:
        arr = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return []
    return [str(g).strip() for g in arr if isinstance(g, str) and str(g).strip()][: cfg.n_goals]


# ---------- M2: per-goal explore loop ----------

def _next_action(goal: str, png: bytes, history: List[str], cfg: ExploreConfig) -> Tuple[str, str]:
    system = (
        f"You are exploring the Ubuntu app '{cfg.app}' (screen {cfg.screen_w}x{cfg.screen_h}). "
        "Move purposefully toward the GOAL. Each turn, given the current screenshot, output ONE JSON "
        '{"thought": "...", "action": "..."} where action is a SINGLE pyautogui command using ABSOLUTE '
        'pixel coordinates (e.g. "pyautogui.click(960, 540)", "pyautogui.write(\'hello\')", '
        '"pyautogui.press(\'enter\')", "pyautogui.hotkey(\'ctrl\',\'s\')"), or "DONE" when the goal is '
        "reached. Do not repeat a previous action."
        + ((" " + CONTEXT_HINT[cfg.app]) if cfg.app in CONTEXT_HINT else "")
    )
    hist = "\n".join(f"{i+1}. {a}" for i, a in enumerate(history)) or "(none yet)"
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": [
            {"type": "text", "text": f"GOAL: {goal}\nactions so far:\n{hist}\nNext action as JSON:"},
            _img_block(png),
        ]},
    ]
    raw = call_gpt(messages, cfg)
    thought, action = "", ""
    start = raw.find("{")
    if start != -1:
        try:  # raw_decode parses ONLY the first JSON object, ignoring extra concatenated ones
            obj, _ = json.JSONDecoder().raw_decode(raw[start:])
            if isinstance(obj, dict):
                thought = str(obj.get("thought", "")).strip()
                action = str(obj.get("action", "")).strip()
        except json.JSONDecodeError:
            pass
    if not action:
        am = ACTION_RE.search(raw)
        action = am.group(0) if am else ("DONE" if "DONE" in raw else "")
    return thought, action


def _save(path: str, data: Any) -> None:
    mode, payload = ("wb", data) if isinstance(data, bytes) else ("w", str(data)[:MAX_A11Y_CHARS])
    with open(path, mode, **({} if isinstance(data, bytes) else {"encoding": "utf-8"})) as fh:
        fh.write(payload)


def explore_one(env: DesktopEnv, goal: str, root_cfg: Dict[str, Any], cfg: ExploreConfig, gi: int) -> Dict[str, Any]:
    traj_dir = os.path.join(cfg.out_dir, cfg.app, f"goal_{gi:03d}")
    os.makedirs(traj_dir, exist_ok=True)
    obs = env.reset(task_config=root_cfg)  # reset to shared root (dominant cost, intended)
    steps: List[Dict[str, Any]] = []
    history: List[str] = []
    end_reason = "max_steps"
    for t in range(cfg.max_steps):
        if not obs or not obs.get("screenshot"):
            end_reason = "bad_obs"
            break
        png_before = obs["screenshot"]
        _save(os.path.join(traj_dir, f"step_{t:02d}_before.png"), png_before)
        if obs.get("accessibility_tree"):
            _save(os.path.join(traj_dir, f"step_{t:02d}_a11y.txt"), obs["accessibility_tree"])
        thought, action = _next_action(goal, png_before, history, cfg)
        if not action or action.upper() == "DONE":
            end_reason = "done"
            break
        if not valid_action(action):
            logger.warning("[%s g%d] step %d invalid action dropped: %s", cfg.app, gi, t, action[:60])
            end_reason = "bad_action"
            break
        if action in history[-3:]:  # stuck: repeating a recent action
            end_reason = "stuck"
            break
        steps.append({"index": t, "thought": thought, "action": action,
                      "img_before": f"step_{t:02d}_before.png", "a11y_before": f"step_{t:02d}_a11y.txt"})
        history.append(action)
        try:
            obs, _, done, _ = env.step(action)
        except Exception as e:  # a bad pyautogui line shouldn't kill the goal
            logger.warning("[%s g%d] step %d action failed: %s", cfg.app, gi, t, e)
            steps[-1]["exec_error"] = str(e)
            end_reason = "exec_error"
            break
        logger.info("[%s g%d] step %d: %s", cfg.app, gi, t, action[:60])
        if done:
            end_reason = "env_done"
            break
    if obs and obs.get("screenshot"):
        _save(os.path.join(traj_dir, "final.png"), obs["screenshot"])
    return {"goal": goal, "app": cfg.app, "n_steps": len(steps), "end_reason": end_reason, "steps": steps, "dir": traj_dir}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--app", required=True, choices=sorted(ROOT_CONFIG))
    parser.add_argument("--provider", default="vmware")
    parser.add_argument("--path-to-vm", default=None)
    parser.add_argument("--n-goals", type=int, default=10)
    parser.add_argument("--max-steps", type=int, default=15)
    parser.add_argument("--screen-width", type=int, default=1920)
    parser.add_argument("--screen-height", type=int, default=1080)
    parser.add_argument("--temperature", type=float, default=1.0)
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--out-dir", default="explore_out")
    args = parser.parse_args()

    if args.n_goals < 1 or args.max_steps < 1:
        parser.error("--n-goals and --max-steps must be >= 1")
    if not os.environ.get("OPENAI_BASE_URL") or not os.environ.get("OPENAI_API_KEY"):
        raise SystemExit("set OPENAI_BASE_URL and OPENAI_API_KEY in env")

    cfg = ExploreConfig(app=args.app, n_goals=args.n_goals, max_steps=args.max_steps,
                        screen_w=args.screen_width, screen_h=args.screen_height,
                        out_dir=args.out_dir, model=os.environ.get("OSWORLD_PROPOSER_MODEL", "gpt-5.5"),
                        temperature=args.temperature)
    root_cfg = {"id": f"explore-root-{args.app}-{uuid.uuid4().hex[:6]}",
                "instruction": f"explore {args.app}", "snapshot": args.app,
                "config": ROOT_CONFIG[args.app], "related_apps": [args.app],
                "evaluator": {"func": "infeasible"}}

    env = DesktopEnv(provider_name=args.provider, path_to_vm=args.path_to_vm, action_space="pyautogui",
                     screen_size=(args.screen_width, args.screen_height), headless=args.headless,
                     os_type="Ubuntu", require_a11y_tree=True)
    trajectories: List[Dict[str, Any]] = []
    try:
        obs0 = env.reset(task_config=root_cfg)
        goals = propose_goals(obs0["screenshot"], cfg)
        if not goals:
            raise SystemExit("M1 propose_goals returned 0 goals (check model output / endpoint)")
        logger.info("proposed %d goals for %s", len(goals), args.app)
        for gi, g in enumerate(goals):
            try:
                trajectories.append(explore_one(env, g, root_cfg, cfg, gi))
            except Exception as e:  # one goal's failure must not kill the batch
                logger.error("goal %d (%s) failed: %s", gi, g[:50], e)
    finally:
        env.close()

    os.makedirs(cfg.out_dir, exist_ok=True)
    out = os.path.join(cfg.out_dir, f"{args.app}_trajectories.jsonl")
    with open(out, "w", encoding="utf-8") as fh:
        for tj in trajectories:
            fh.write(json.dumps(tj, ensure_ascii=False) + "\n")
    by_reason: Dict[str, int] = {}
    for tj in trajectories:
        by_reason[tj["end_reason"]] = by_reason.get(tj["end_reason"], 0) + 1
    logger.info("wrote %d trajectories -> %s | end_reasons=%s", len(trajectories), out, by_reason)
    logger.info("NEXT: M3 state-diff per step (screenshot+a11y) -> M4 reverse task synthesis.")


if __name__ == "__main__":
    main()
