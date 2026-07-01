"""AgentNet trajectory -> multimodal skill (traj2skill).

DISTILL (not translate) reusable multimodal skills from complete AgentNet human
trajectories, per doc/skill_schema.md. An MLLM (GPT-5.5) reads the WHOLE trajectory
and EXTRACTS the reusable skill(s) inside it (it decides how many), applying MILD
abstraction: keep the concrete procedure + UI targets, but lift task-specific values
(filenames, entered text, target names) into {parameter} slots. Visual anchors are
grounded on the real screenshots only for the steps that need them (L1 vision).

Pipeline per trajectory:
  adapt   AgentNet record -> normalized {task, steps:[{image, code, thought, action,
          reflection}]}, dropping steps flagged redundant.
  Pass-1  text-only distillation: MLLM -> list of skills; each step references its
          source trajectory step and carries intent/target/anchor?/verify?.
  Pass-2  L1 vision: for anchor steps, read the screenshot + click point -> confirm
          and tighten bbox_norm + semantic target (falls back to a coord box if the
          screenshot is not available locally).

Endpoint from env: OPENAI_BASE_URL, OPENAI_API_KEY, OSWORLD_PROPOSER_MODEL (gpt-5.5).

Run:
  python agentnet_traj2skill.py --in agentnet_ubuntu_5k.jsonl \
      --img-dirs batch_imgs,test_imgs --out agentnet_skills.jsonl --limit 20
"""

from __future__ import annotations

import argparse
import base64
import json
import logging
import os
import re
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import requests

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

_NUM = r"[-+]?\d*\.?\d+"
_VERB_MAP = {"click": "click", "doubleClick": "double_click", "rightClick": "right_click",
             "moveTo": "move", "dragTo": "drag", "scroll": "scroll", "hotkey": "hotkey",
             "press": "press", "typewrite": "type", "write": "type"}


@dataclass(frozen=True)
class T2SConfig:
    in_path: str
    img_dirs: Tuple[str, ...]
    out_path: str
    model: str
    temperature: float
    limit: int
    min_alignment: int
    require_images: bool
    use_vision: bool


# ---------- GPT-5.5 ----------

def _img_block(png: bytes) -> Dict[str, Any]:
    uri = "data:image/png;base64," + base64.b64encode(png).decode("utf-8")
    return {"type": "image_url", "image_url": {"url": uri}}


def call_gpt(messages: List[Dict[str, Any]], cfg: T2SConfig, retries: int = 5) -> str:
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


def _extract_json(raw: str) -> Optional[Any]:
    """Parse the first DECODABLE JSON object/array in a model reply.

    Scans every '{'/'[' start (not just the first) so a stray brace in prose before
    the real JSON does not silently yield None.
    """
    raw = re.sub(r"```(?:json)?", "", raw)
    for s in (i for i, c in enumerate(raw) if c in "{["):
        try:
            obj, _ = json.JSONDecoder().raw_decode(raw[s:])
            return obj
        except json.JSONDecodeError:
            continue
    return None


def _read_bytes(path: str) -> Optional[bytes]:
    try:
        with open(path, "rb") as fh:
            return fh.read()
    except OSError:
        return None


# ---------- pyautogui code parsing ----------

def parse_code(code: str) -> Dict[str, Any]:
    """pyautogui.<fn>(...) -> {verb, value, x, y} (coords already normalized 0-1).

    Assumes ONE pyautogui statement per step (AgentNet's format); the first call is
    parsed if more are present.
    """
    m = re.search(r"pyautogui\.(\w+)\((.*)\)", (code or "").strip(), re.S)
    if not m:
        return {"verb": "unknown", "value": "", "x": None, "y": None}
    fn, args = m.group(1), m.group(2)
    verb = _VERB_MAP.get(fn, fn)
    value = ""
    if verb == "type":
        vm = re.search(r"""(['"])(.*?)\1""", args, re.S)  # first string literal, non-greedy
        value = vm.group(2) if vm else ""
    elif verb in ("hotkey", "press"):
        value = "+".join(re.findall(r"""['"]([^'"]+)['"]""", args))
    elif verb == "scroll":
        sm = re.search(rf"({_NUM})", args)
        value = sm.group(1) if sm else ""
    xm = re.search(rf"x\s*=\s*({_NUM})", args)
    ym = re.search(rf"y\s*=\s*({_NUM})", args)
    if xm is None and ym is None and verb in ("click", "double_click", "right_click", "move", "drag"):
        pos = re.findall(_NUM, args)  # positional coords: click(0.018, 0.508)
        x = float(pos[0]) if len(pos) >= 2 else None
        y = float(pos[1]) if len(pos) >= 2 else None
    else:
        x = float(xm.group(1)) if xm else None
        y = float(ym.group(1)) if ym else None
    return {"verb": verb, "value": value, "x": x, "y": y}


def _point_box(x: float, y: float, w: float = 0.04, h: float = 0.04) -> List[float]:
    return [round(max(0.0, x - w / 2), 4), round(max(0.0, y - h / 2), 4), w, h]


# ---------- adapter: AgentNet record -> normalized trajectory ----------

def find_images(img_dirs: Tuple[str, ...]) -> Dict[str, str]:
    idx: Dict[str, str] = {}
    for d in img_dirs:
        if os.path.isdir(d):
            for f in os.listdir(d):
                if f.endswith(".png"):
                    idx.setdefault(f, os.path.join(d, f))
    return idx


def normalize(rec: Dict[str, Any]) -> Dict[str, Any]:
    steps: List[Dict[str, Any]] = []
    for st in rec.get("traj", []):
        v = st.get("value", {})
        if v.get("last_step_redundant"):
            continue
        steps.append({"index": st.get("index"), "image": st.get("image", ""),
                      "code": v.get("code", ""), "thought": v.get("thought", ""),
                      "action": v.get("action", ""), "reflection": v.get("reflection", "")})
    return {"task_id": rec.get("task_id", ""),
            "task": rec.get("actual_task") or rec.get("natural_language_task") or rec.get("instruction", ""),
            "difficulty": rec.get("task_difficulty"), "alignment": rec.get("alignment_score"),
            "steps": steps}


def select(cfg: T2SConfig, img_index: Dict[str, str]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    with open(cfg.in_path, encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            rec = json.loads(line)
            if not rec.get("task_completed"):
                continue
            if (rec.get("alignment_score") or 0) < cfg.min_alignment:
                continue
            if cfg.require_images and any(st.get("image") not in img_index for st in rec.get("traj", [])):
                continue
            out.append(normalize(rec))
            if len(out) >= cfg.limit:
                break
    return out


# ---------- Pass-1: distill reusable skill(s) from the whole trajectory ----------

SKILL_SYS = (
    "You are given ONE complete human trajectory that accomplishes a desktop task on Ubuntu: the TASK, then "
    "per-step {thought, action, code, reflection}. EXTRACT the reusable multimodal SKILL(S) this trajectory "
    "demonstrates -- DISTILL, do not transcribe. Rules:\n"
    "- A skill is a REUSABLE competence (a coherent how-to applicable to other, similar tasks), NOT a replay "
    "of this run. Decide how many skills this trajectory contains (usually 1, sometimes a few) and return each.\n"
    "- MILD ABSTRACTION: keep the concrete procedure and its UI targets, but replace task-specific VALUES "
    "(filenames, entered text, search terms, specific target names) with {parameter} slots, and list them in "
    "'parameters'.\n"
    "- Keep ONLY the essential steps; DROP glue / navigation / backtracking. One step = ONE action (do not merge "
    "actions); you MAY drop steps. Each skill step MUST reference its 'source_step' (the trajectory step index).\n"
    "- Per step decide: needs_anchor (true if the target is a specific on-screen element that must be seen to "
    "locate, e.g. an icon or menu item; false for obvious/global targets or keyboard actions); needs_verify "
    "(true only for steps producing a meaningful, checkable state change) + a short 'verify_cue'.\n"
    "- intent = the step's purpose; target = a semantic description of what is acted on (NO coordinates).\n"
    'Return ONLY JSON: {"skills": [{"name": "snake_case_verb_phrase", "description": "...", '
    '"domain": "gimp|chrome|libreoffice_calc|libreoffice_writer|libreoffice_impress|vlc|vs_code|thunderbird|os|multi_apps", '
    '"preconditions": ["..."], "parameters": [{"name": "...", "example": "..."}], "steps": [{"source_step": int, '
    '"intent": "...", "target": "...", "needs_anchor": true, "needs_verify": false, "verify_cue": ""}]}]}'
)


def distill(traj: Dict[str, Any], cfg: T2SConfig) -> List[Dict[str, Any]]:
    lines = [
        f"[step {st['index']}] thought: {st['thought'][:220]}\n"
        f"  action: {st['action'][:180]}\n  code: {st['code']}\n"
        f"  reflection: {st['reflection'][:180]}"
        for st in traj["steps"]
    ]
    body = (f"TASK: {traj['task']}\n\nTRAJECTORY ({len(traj['steps'])} kept steps):\n"
            + "\n".join(lines) + "\n\nExtract the reusable skill(s) as JSON.")
    raw = call_gpt([{"role": "system", "content": SKILL_SYS}, {"role": "user", "content": body}], cfg)
    obj = _extract_json(raw)
    skills = obj.get("skills", []) if isinstance(obj, dict) else []
    return [s for s in skills if isinstance(s, dict) and s.get("steps")]


# ---------- Pass-2: L1 vision grounding of an anchor ----------

ANCHOR_SYS = (
    "A skill step acts on a specific on-screen element. Given the screenshot and a click point (normalized "
    "0-1), confirm the element at/near the point matches the described target and return a TIGHT normalized "
    'bounding box around that target element. Return ONLY JSON {"confirmed": true, "bbox_norm": [x, y, w, h], '
    '"target": "corrected-or-same short description"}.'
)


def ground_anchor(target: str, point: Tuple[float, float], img_path: str,
                  cfg: T2SConfig) -> Optional[Dict[str, Any]]:
    png = _read_bytes(img_path)
    if not png:
        return None
    user = [{"type": "text", "text": f"Click point: x={point[0]}, y={point[1]}. Target: {target[:150]}"},
            _img_block(png)]
    obj = _extract_json(call_gpt([{"role": "system", "content": ANCHOR_SYS},
                                  {"role": "user", "content": user}], cfg))
    return obj if isinstance(obj, dict) else None


# ---------- assemble final skills ----------

def build(traj: Dict[str, Any], skills: List[Dict[str, Any]], img_index: Dict[str, str],
          cfg: T2SConfig) -> Tuple[List[Dict[str, Any]], int, int]:
    step_by_idx = {st["index"]: st for st in traj["steps"]}
    built: List[Dict[str, Any]] = []
    grounded = fallback = 0
    for sk in skills:
        steps_out: List[Dict[str, Any]] = []
        for ss in sk.get("steps", []):
            try:
                key: Any = int(ss.get("source_step"))
            except (TypeError, ValueError):
                key = ss.get("source_step")
            src = step_by_idx.get(key)
            if src is None:
                logger.debug("drop step: unknown source_step %r (task %s)",
                             ss.get("source_step"), traj["task_id"][:8])
                continue
            pc = parse_code(src["code"])
            step: Dict[str, Any] = {
                "intent": str(ss.get("intent", "")),
                "action": {"verb": pc["verb"], "target": str(ss.get("target", "")), "value": pc["value"]},
            }
            if ss.get("needs_anchor") and pc["x"] is not None:
                anchor = {"frame_ref": src["image"], "bbox_norm": _point_box(pc["x"], pc["y"])}
                grounded_ok = False
                if cfg.use_vision:
                    g = ground_anchor(step["action"]["target"], (pc["x"], pc["y"]),
                                      img_index.get(src["image"], ""), cfg)
                    if g and isinstance(g.get("bbox_norm"), list) and len(g["bbox_norm"]) == 4:
                        try:
                            anchor["bbox_norm"] = [round(min(1.0, max(0.0, float(c))), 4) for c in g["bbox_norm"]]
                            if g.get("target"):
                                step["action"]["target"] = str(g["target"])
                            grounded_ok = True
                        except (TypeError, ValueError):
                            grounded_ok = False
                grounded += int(grounded_ok)
                fallback += int(not grounded_ok)
                step["visual_anchor"] = anchor
            if ss.get("needs_verify") and ss.get("verify_cue"):
                step["verification"] = {"cue": str(ss["verify_cue"]), "frame_ref": src["image"]}
            steps_out.append(step)
        if not steps_out:
            continue
        built.append({
            "name": str(sk.get("name", "")),
            "description": str(sk.get("description", "")),
            "domain": str(sk.get("domain", "")),
            "preconditions": [str(p) for p in sk.get("preconditions", []) if isinstance(p, str)],
            "parameters": [p for p in sk.get("parameters", []) if isinstance(p, dict)],
            "steps": steps_out,
            "provenance": {"dataset": "agentnet", "task_id": traj["task_id"],
                           "source_steps": [ss.get("source_step") for ss in sk.get("steps", [])]},
        })
    return built, grounded, fallback


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--in", dest="in_path", required=True, help="AgentNet ubuntu jsonl")
    parser.add_argument("--img-dirs", default="batch_imgs,test_imgs", help="comma-separated screenshot dirs")
    parser.add_argument("--out", required=True, help="output skills jsonl")
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--min-alignment", type=int, default=8)
    parser.add_argument("--temperature", type=float, default=0.4)
    parser.add_argument("--require-images", action="store_true", help="only trajectories with all frames present")
    parser.add_argument("--no-vision", action="store_true", help="skip L1 vision grounding (coord box only)")
    args = parser.parse_args()

    if args.limit < 1:
        parser.error("--limit must be >= 1")
    if not os.environ.get("OPENAI_BASE_URL") or not os.environ.get("OPENAI_API_KEY"):
        raise SystemExit("set OPENAI_BASE_URL and OPENAI_API_KEY in env")

    cfg = T2SConfig(in_path=args.in_path,
                    img_dirs=tuple(d.strip() for d in args.img_dirs.split(",") if d.strip()),
                    out_path=args.out, model=os.environ.get("OSWORLD_PROPOSER_MODEL", "gpt-5.5"),
                    temperature=args.temperature, limit=args.limit, min_alignment=args.min_alignment,
                    require_images=args.require_images, use_vision=not args.no_vision)

    img_index = find_images(cfg.img_dirs)
    logger.info("indexed %d screenshots from %s", len(img_index), list(cfg.img_dirs))
    try:
        trajs = select(cfg, img_index)
    except FileNotFoundError:
        raise SystemExit(f"input not found: {cfg.in_path}")
    logger.info("selected %d trajectories (completed, alignment>=%d)", len(trajs), cfg.min_alignment)

    all_skills: List[Dict[str, Any]] = []
    tot_grounded = tot_fallback = 0
    for i, tj in enumerate(trajs):
        try:
            skills = distill(tj, cfg)
            built, g, f = build(tj, skills, img_index, cfg)
        except Exception as e:  # one trajectory must not kill the batch
            logger.error("traj %s failed: %s", tj.get("task_id", "")[:8], e, exc_info=True)
            continue
        all_skills.extend(built)
        tot_grounded += g
        tot_fallback += f
        logger.info("[%d/%d] %s (%d steps) -> %d skill(s)", i + 1, len(trajs),
                    tj.get("task_id", "")[:8], len(tj["steps"]), len(built))

    with open(cfg.out_path, "w", encoding="utf-8") as fh:
        for sk in all_skills:
            fh.write(json.dumps(sk, ensure_ascii=False) + "\n")
    logger.info("wrote %d skills -> %s | anchors: %d vision-grounded, %d coord-fallback",
                len(all_skills), cfg.out_path, tot_grounded, tot_fallback)


if __name__ == "__main__":
    main()
