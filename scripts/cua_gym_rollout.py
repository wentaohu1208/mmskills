"""CUA-Gym task -> agent rollout -> tagged trajectory (the rollout runner, "D").

Drive OSWorld's Ubuntu docker VM over CUA-Gym DESKTOP tasks. For each task:
  1. set up the VM from the task's own initial_setup script (uploaded + executed);
  2. let GPT-5.5 attempt the task, recording per step the screenshot + the executed
     pyautogui action + the model's raw thinking;
  3. run the task's self-contained reward.py INSIDE the VM to get a deterministic 0-1 score.

EVERY rollout is KEPT and TAGGED (reward, outcome, app / difficulty / steps / end_reason);
nothing is deleted. A downstream view feeds only successes (reward == 1.0) to the traj->skill
pipeline, while failures/partials stay in the library for later failure-mode mining.

Per step we store screenshot + executed action + raw thinking. The traj->skill pipeline today
reads only screenshot + action; the thinking field rides along for a future upgrade (few -> many).

Trajectory layout matches osworld_explorer / osworld_eval (traj.jsonl + step_*.png), so the
existing 3-way VLM judge (osworld_eval.py) can refine the env_fail tag over this output.

Endpoint (OpenAI-compatible, vision) from env:
  OPENAI_BASE_URL, OPENAI_API_KEY, OSWORLD_PROPOSER_MODEL (default 'gpt-5.5').

Run (needs a live OSWorld VM):
  python cua_gym_rollout.py --tasks-root /data/hwt/hf_data/CUA-Gym/extracted \
      --apps libreoffice_calc --limit 10 --provider docker \
      --path-to-vm /data/hwt/OSWorld/docker_vm_data/Ubuntu.qcow2 --out-dir rollouts_calc
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
from typing import Any, Dict, List, Optional, Tuple

import requests

from desktop_env.desktop_env import DesktopEnv

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

ACTION_RE = re.compile(r"pyautogui\.[A-Za-z]+\([^\n;]*\)")
_DANGER = ("os.", "import", "subprocess", "exec", "eval", "__")
_REWARD_RE = re.compile(r"REWARD:\s*([+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?)")


@dataclass(frozen=True)
class RolloutConfig:
    tasks_root: str
    apps: Optional[Tuple[str, ...]]
    limit: int
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


def call_gpt(messages: List[Dict[str, Any]], cfg: RolloutConfig, retries: int = 5) -> str:
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


# ---------- action proposal ----------

def valid_action(a: str) -> bool:
    """Gate an LLM action: only a single bare pyautogui.<fn>(...) call, or DONE."""
    a = a.strip()
    if a.upper() == "DONE":
        return True
    if not a.startswith("pyautogui.") or ";" in a or "\n" in a:
        return False
    head = a.split("(", 1)[0]  # call target only -- never the typed args, e.g. write('important')
    if any(bad in head for bad in _DANGER):
        return False
    return bool(re.fullmatch(r"pyautogui\.[A-Za-z]+\(.*\)", a))


def next_action(instruction: str, app: str, png: bytes, history: List[str],
                cfg: RolloutConfig) -> Tuple[str, str]:
    """One GPT-5.5 turn -> (thought, action). Action = a single ABSOLUTE-pixel pyautogui call, or DONE."""
    system = (
        f"You are completing a TASK on the Ubuntu app '{app}' (screen {cfg.screen_w}x{cfg.screen_h}). "
        "Work step by step toward finishing the task. Each turn, given the current screenshot, output ONE "
        'JSON {"thought": "...", "action": "..."} where action is a SINGLE pyautogui command using ABSOLUTE '
        "pixel coordinates (e.g. \"pyautogui.click(960, 540)\", \"pyautogui.write('hello')\", "
        "\"pyautogui.press('enter')\", \"pyautogui.hotkey('ctrl','s')\"), or \"DONE\" when the task is fully "
        "complete. If the task changes a document, SAVE it before DONE. Do not repeat a previous action."
    )
    hist = "\n".join(f"{i + 1}. {a}" for i, a in enumerate(history)) or "(none yet)"
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": [
            {"type": "text", "text": f"TASK: {instruction}\nactions so far:\n{hist}\nNext action as JSON:"},
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


# ---------- CUA-Gym task loading + OSWorld task_config ----------

def load_tasks(cfg: RolloutConfig) -> List[Dict[str, Any]]:
    """Load CUA-Gym task bundles under tasks_root, optionally filtered to `apps`, up to `limit`."""
    out: List[Dict[str, Any]] = []
    for tj in sorted(glob.glob(os.path.join(cfg.tasks_root, "*", "task.json"))):
        try:
            with open(tj, encoding="utf-8") as fh:
                t = json.load(fh)
        except (OSError, json.JSONDecodeError) as e:
            logger.warning("skip unreadable task %s: %s", tj, e)
            continue
        app = t.get("app_type")
        if cfg.apps and app not in cfg.apps:
            continue
        d = os.path.dirname(tj)
        out.append({"id": t.get("id") or os.path.basename(d), "instruction": t.get("instruction", ""),
                    "app_type": app, "difficulty": t.get("difficulty"), "dir": d})
        if cfg.limit and len(out) >= cfg.limit:
            break
    return out


def _setup_files(task_dir: str) -> Tuple[List[Tuple[str, str]], Optional[Tuple[str, str]]]:
    """Return ([(local_path, vm_name), ...], (runner, vm_name) | None) for the initial_setup.* files."""
    uploads: List[Tuple[str, str]] = []
    runner: Optional[Tuple[str, str]] = None
    for p in sorted(glob.glob(os.path.join(task_dir, "initial_setup.*"))):
        name = os.path.basename(p)
        uploads.append((p, name))
        if runner is None and name.endswith(".py"):
            runner = ("python3", name)
        elif runner is None and name.endswith(".sh"):
            runner = ("bash", name)
    return uploads, runner


def build_task_config(task: Dict[str, Any]) -> Dict[str, Any]:
    """OSWorld task_config that uploads the task's setup + reward files into the VM and runs setup.

    We do NOT use OSWorld's own evaluator here: scoring is done post-rollout by running the task's
    reward.py inside the VM (score_task). The placeholder evaluator keeps env.reset happy.
    """
    d = task["dir"]
    uploads, runner = _setup_files(d)
    files = [{"local_path": os.path.abspath(local), "path": f"/home/user/{name}"} for local, name in uploads]
    reward_path = os.path.join(d, "reward.py")
    if os.path.isfile(reward_path):
        files.append({"local_path": os.path.abspath(reward_path), "path": "/home/user/reward.py"})
    config: List[Dict[str, Any]] = []
    if files:
        config.append({"type": "upload_file", "parameters": {"files": files}})
    if runner:
        cmd, name = runner
        # run in /home/user so relative-path setups land where reward.py (also cd'd there) looks for them
        config.append({"type": "execute", "parameters": {
            "command": f"cd /home/user && {cmd} /home/user/{name}", "shell": True}})
    else:
        logger.warning("task %s has no initial_setup.py/.sh runner -> app not launched; likely scores 0",
                       str(task["id"])[:8])
    return {"id": task["id"], "instruction": task["instruction"], "snapshot": task["app_type"],
            "config": config, "related_apps": [task["app_type"]], "evaluator": {"func": "infeasible"}}


# ---------- deterministic reward (run the task's reward.py inside the VM) ----------

# reward.py prints "REWARD: <float>". run_bash_script is broken in the shipped VM image, so run reward.py
# via the (working) python endpoint: exec its __main__ with stdout redirected to a VM file we pull back.
_REWARD_OUT = "/home/user/_reward_out.txt"
_REWARD_DRIVER = (
    "import io, contextlib, runpy\n"
    "buf = io.StringIO()\n"
    "try:\n"
    "    with contextlib.redirect_stdout(buf):\n"
    f"        runpy.run_path('/home/user/reward.py', run_name='__main__')\n"
    "except SystemExit:\n"
    "    pass\n"
    "except Exception as _e:\n"
    "    buf.write('RUNERR: ' + str(_e))\n"
    f"with open('{_REWARD_OUT}', 'w') as _f:\n"
    "    _f.write(buf.getvalue())\n"
)


def score_task(env: DesktopEnv) -> Optional[float]:
    """Run the task's reward.py inside the VM and parse its 'REWARD: <float>' line. None if unavailable."""
    try:
        env.controller.run_python_script(_REWARD_DRIVER)
        raw = env.controller.get_file(_REWARD_OUT)
    except Exception as e:  # scoring failure must not kill the batch  # noqa: BLE001
        logger.warning("reward.py run failed: %s", e)
        return None
    if not raw:
        logger.warning("reward.py produced no output")
        return None
    out = raw.decode("utf-8", "ignore")
    matches = _REWARD_RE.findall(out)
    if not matches:
        logger.warning("no REWARD line in reward.py output: %s", out.strip()[:200])
        return None
    return float(matches[-1])  # regex guarantees a float-parseable capture


# ---------- one rollout ----------

def _save_png(path: str, png: bytes) -> None:
    with open(path, "wb") as fh:
        fh.write(png)


def run_task(env: DesktopEnv, task: Dict[str, Any], cfg: RolloutConfig) -> Dict[str, Any]:
    """Set up -> GPT-5.5 rollout (screenshot + action + thinking per step) -> reward -> tagged episode dir."""
    safe_id = re.sub(r"[^\w.-]", "_", str(task["id"]))  # never let a dataset id escape out_dir
    ep_dir = os.path.join(cfg.out_dir, str(task["app_type"]), safe_id)
    os.makedirs(ep_dir, exist_ok=True)
    obs = env.reset(task_config=build_task_config(task))
    steps: List[Dict[str, Any]] = []
    history: List[str] = []
    end_reason = "max_steps"
    for t in range(cfg.max_steps):
        if not obs or not obs.get("screenshot"):
            end_reason = "bad_obs"
            break
        png = obs["screenshot"]
        _save_png(os.path.join(ep_dir, f"step_{t:02d}_before.png"), png)
        thought, action = next_action(task["instruction"], task["app_type"], png, history, cfg)
        if not action:
            end_reason = "no_action"
            break
        if action.upper() == "DONE":
            end_reason = "done"
            break
        if not valid_action(action):
            logger.warning("[%s] step %d invalid action dropped: %s", task["id"][:8], t, action[:60])
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
        except Exception as e:  # a bad pyautogui line shouldn't kill the task  # noqa: BLE001
            logger.warning("[%s] step %d action failed: %s", task["id"][:8], t, e)
            steps[-1]["exec_error"] = str(e)
            end_reason = "exec_error"
            break
        logger.info("[%s] step %d: %s", task["id"][:8], t, action[:60])
        if done:
            end_reason = "env_done"
            break
    if obs and obs.get("screenshot"):
        _save_png(os.path.join(ep_dir, "final.png"), obs["screenshot"])
    with open(os.path.join(ep_dir, "traj.jsonl"), "w", encoding="utf-8") as fh:
        for s in steps:
            fh.write(json.dumps(s, ensure_ascii=False) + "\n")

    reward = score_task(env)
    outcome = "success" if reward is not None and reward >= 1.0 else \
              ("capability_fail" if reward is not None else "unscored")
    tags = {"task_id": task["id"], "app_type": task["app_type"], "difficulty": task.get("difficulty"),
            "instruction": task["instruction"], "reward": reward, "outcome": outcome,
            "n_steps": len(steps), "end_reason": end_reason, "dir": ep_dir}
    with open(os.path.join(ep_dir, "tags.json"), "w", encoding="utf-8") as fh:
        json.dump(tags, fh, ensure_ascii=False, indent=2)
    return tags


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tasks-root", required=True, help="CUA-Gym extracted task bundles dir")
    parser.add_argument("--apps", default=None, help="comma-separated app_type filter (e.g. libreoffice_calc)")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--max-steps", type=int, default=20)
    parser.add_argument("--provider", default="docker")
    parser.add_argument("--path-to-vm", default=None)
    parser.add_argument("--screen-width", type=int, default=1920)
    parser.add_argument("--screen-height", type=int, default=1080)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--out-dir", default="rollouts")
    args = parser.parse_args()

    if args.limit < 1 or args.max_steps < 1:
        parser.error("--limit and --max-steps must be >= 1")
    if not os.environ.get("OPENAI_BASE_URL") or not os.environ.get("OPENAI_API_KEY"):
        raise SystemExit("set OPENAI_BASE_URL and OPENAI_API_KEY in env")

    cfg = RolloutConfig(
        tasks_root=args.tasks_root,
        apps=tuple(a.strip() for a in args.apps.split(",") if a.strip()) if args.apps else None,
        limit=args.limit, max_steps=args.max_steps, screen_w=args.screen_width, screen_h=args.screen_height,
        out_dir=args.out_dir, model=os.environ.get("OSWORLD_PROPOSER_MODEL", "gpt-5.5"),
        temperature=args.temperature,
    )
    tasks = load_tasks(cfg)
    if not tasks:
        raise SystemExit(f"no tasks matched under {cfg.tasks_root} (apps={cfg.apps})")
    logger.info("loaded %d tasks (apps=%s)", len(tasks), cfg.apps)

    env = DesktopEnv(provider_name=args.provider, path_to_vm=args.path_to_vm, action_space="pyautogui",
                     screen_size=(args.screen_width, args.screen_height), headless=args.headless,
                     os_type="Ubuntu", require_a11y_tree=False)
    results: List[Dict[str, Any]] = []
    try:
        for i, task in enumerate(tasks):
            try:
                tags = run_task(env, task, cfg)
                results.append(tags)
                logger.info("[%d/%d] %s reward=%s outcome=%s steps=%d",
                            i + 1, len(tasks), str(task["id"])[:8], tags["reward"], tags["outcome"], tags["n_steps"])
            except Exception as e:  # one task's failure must not kill the batch  # noqa: BLE001
                logger.error("task %s failed: %s", str(task["id"])[:8], e, exc_info=True)
                results.append({"task_id": task["id"], "app_type": task.get("app_type"),
                                "difficulty": task.get("difficulty"), "instruction": task.get("instruction", ""),
                                "reward": None, "outcome": "error", "n_steps": 0,
                                "end_reason": "exception", "error": str(e)})  # keep-all: tag the failure too
    finally:
        env.close()

    os.makedirs(cfg.out_dir, exist_ok=True)
    index = os.path.join(cfg.out_dir, "rollouts_index.jsonl")
    with open(index, "w", encoding="utf-8") as fh:
        for r in results:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    n_success = sum(1 for r in results if r.get("outcome") == "success")
    n_scored = sum(1 for r in results if r.get("reward") is not None)
    logger.info("done: %d rollouts | scored=%d success=%d -> %s", len(results), n_scored, n_success, index)
    logger.info("NEXT: feed reward==1.0 episodes to traj2skill; run osworld_eval.py for the env_fail tag.")


if __name__ == "__main__":
    main()
