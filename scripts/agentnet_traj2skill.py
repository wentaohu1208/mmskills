"""AgentNet trajectory -> multimodal skill (traj2skill).

Treat AgentNet as a MINIMAL rollout trajectory: use ONLY the per-step screenshot and
the executed action (verb + normalized coords + value); IGNORE its rich human/model
annotations (thought, reflection, quality flags). This matches what a real agent
rollout actually gives you, and makes it easy to feed richer fields later (few -> many).

Two stages:
  (1) ENRICH  per step, MLLM + vision (the ONLY vision stage). From [before frame,
      after frame, action] -> {target (semantic), effect, anchor_bbox (tight box on the
      target on the BEFORE frame; pointer actions only), change_bbox (changed region on
      the AFTER frame; null if diffuse)}. Turns raw pixels+coords into text + boxes.
  (2) DISTILL  whole trajectory, MLLM, TEXT-ONLY (no vision). From task + enriched steps
      -> reusable multimodal skill(s): the model decides how many, applies mild
      abstraction (values -> {parameters}), drops glue steps, sets per-step intent /
      needs_anchor / verification.

Output: one FOLDER per skill -- <NNN>_<name>/skill.json + frames/ (full screenshots).
All skill content is ENGLISH.

Endpoint from env: OPENAI_BASE_URL, OPENAI_API_KEY, OSWORLD_PROPOSER_MODEL (gpt-5.5).

Run:
  python agentnet_traj2skill.py --in agentnet_ubuntu_5k.jsonl \
      --img-dirs batch_imgs,test_imgs --out-dir outputs/agentnet_skills_v2 --limit 20
"""

from __future__ import annotations

import argparse
import base64
import json
import logging
import os
import re
import shutil
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
_POINTER = {"click", "double_click", "right_click", "move", "drag"}


@dataclass(frozen=True)
class T2SConfig:
    in_path: str
    img_dirs: Tuple[str, ...]
    out_dir: str
    model: str
    temperature: float
    limit: int
    min_alignment: int
    require_images: bool


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
    """Parse the first decodable JSON object/array in a model reply."""
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


# ---------- helpers ----------

def parse_code(code: str) -> Dict[str, Any]:
    """pyautogui.<fn>(...) -> {verb, value, x, y} (coords already normalized 0-1)."""
    m = re.search(r"pyautogui\.(\w+)\((.*)\)", (code or "").strip(), re.S)
    if not m:
        return {"verb": "unknown", "value": "", "x": None, "y": None}
    fn, args = m.group(1), m.group(2)
    verb = _VERB_MAP.get(fn, fn)
    value = ""
    if verb == "type":
        vm = re.search(r"""(['"])(.*?)\1""", args, re.S)
        value = vm.group(2) if vm else ""
    elif verb in ("hotkey", "press"):
        value = "+".join(re.findall(r"""['"]([^'"]+)['"]""", args))
    elif verb == "scroll":
        sm = re.search(rf"({_NUM})", args)
        value = sm.group(1) if sm else ""
    xm = re.search(rf"x\s*=\s*({_NUM})", args)
    ym = re.search(rf"y\s*=\s*({_NUM})", args)
    if xm is None and ym is None and verb in _POINTER:
        pos = re.findall(_NUM, args)
        x = float(pos[0]) if len(pos) >= 2 else None
        y = float(pos[1]) if len(pos) >= 2 else None
    else:
        x = float(xm.group(1)) if xm else None
        y = float(ym.group(1)) if ym else None
    return {"verb": verb, "value": value, "x": x, "y": y}


def _clamp_box(b: Any) -> Optional[List[float]]:
    if not (isinstance(b, list) and len(b) == 4):
        return None
    try:
        return [round(min(1.0, max(0.0, float(c))), 4) for c in b]
    except (TypeError, ValueError):
        return None


def _sanitize(name: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]+", "_", name.strip().lower()).strip("_")[:60] or "skill"


# ---------- adapter: AgentNet record -> minimal trajectory ----------

def find_images(img_dirs: Tuple[str, ...]) -> Dict[str, str]:
    idx: Dict[str, str] = {}
    for d in img_dirs:
        if os.path.isdir(d):
            for f in os.listdir(d):
                if f.endswith(".png"):
                    idx.setdefault(f, os.path.join(d, f))
    return idx


def normalize(rec: Dict[str, Any]) -> Dict[str, Any]:
    """Keep ONLY {index, image, code} per step -- treat as a bare rollout."""
    steps = [{"index": st.get("index"), "image": st.get("image", ""),
              "code": st.get("value", {}).get("code", "")} for st in rec.get("traj", [])]
    return {"task_id": rec.get("task_id", ""),
            "task": rec.get("actual_task") or rec.get("natural_language_task") or rec.get("instruction", ""),
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


# ---------- (1) ENRICH: per-step vision -> text + boxes ----------

ENRICH_SYS = (
    "You see the screen BEFORE an action, the screen AFTER it, and the action (a pyautogui verb + normalized "
    "0-1 click point + value). Describe, in ENGLISH, what this ONE step did. Return ONLY JSON: "
    '{"target": "<semantic description of the on-screen element acted on; for keyboard actions describe the '
    'focused context>", "effect": "<one sentence: what changed from BEFORE to AFTER>", "anchor_bbox": '
    "[x,y,w,h] or null, \"change_bbox\": [x,y,w,h] or null}. anchor_bbox = a TIGHT normalized box around the "
    "TARGET element on the BEFORE screen (null for keyboard/scroll actions with no visual target). change_bbox "
    "= normalized box of the CHANGED region on the AFTER screen (null if the change is diffuse: a new window, "
    "a full-screen repaint, or an app switch)."
)


def enrich_step(before: Optional[bytes], after: Optional[bytes], pc: Dict[str, Any],
                cfg: T2SConfig) -> Dict[str, Any]:
    parts: List[Dict[str, Any]] = [{"type": "text", "text":
        f"ACTION: verb={pc['verb']} point=({pc['x']},{pc['y']}) value={pc['value']!r}\n(BEFORE, then AFTER)"}]
    if before:
        parts.append(_img_block(before))
    if after:
        parts.append(_img_block(after))
    obj = _extract_json(call_gpt([{"role": "system", "content": ENRICH_SYS},
                                  {"role": "user", "content": parts}], cfg))
    if not isinstance(obj, dict):
        return {"target": "", "effect": "", "anchor_bbox": None, "change_bbox": None}
    return {"target": str(obj.get("target", "")), "effect": str(obj.get("effect", "")),
            "anchor_bbox": _clamp_box(obj.get("anchor_bbox")), "change_bbox": _clamp_box(obj.get("change_bbox"))}


def enrich_traj(traj: Dict[str, Any], img_index: Dict[str, str], cfg: T2SConfig) -> List[Dict[str, Any]]:
    steps = traj["steps"]
    enriched: List[Dict[str, Any]] = []
    for i, st in enumerate(steps):
        pc = parse_code(st["code"])
        before_name = st["image"]
        after_name = steps[i + 1]["image"] if i + 1 < len(steps) else ""
        before = _read_bytes(img_index.get(before_name, ""))
        after = _read_bytes(img_index.get(after_name, "")) if after_name else None
        e = enrich_step(before, after, pc, cfg)
        if pc["verb"] not in _POINTER:  # keyboard/scroll actions never carry an anchor box
            e["anchor_bbox"] = None
        enriched.append({"index": st["index"], "verb": pc["verb"], "value": pc["value"],
                         "target": e["target"], "effect": e["effect"],
                         "anchor_bbox": e["anchor_bbox"], "change_bbox": e["change_bbox"],
                         "before_image": before_name, "after_image": after_name})
    return enriched


# ---------- (2) DISTILL: whole-trajectory text -> reusable skill(s) ----------

DISTILL_SYS = (
    "You are given a TASK and an agent's step-by-step trajectory that accomplished it; each step lists "
    "{verb, value, target (the element acted on), effect (what changed)}. EXTRACT the reusable multimodal "
    "SKILL(S) this trajectory demonstrates -- DISTILL, do not transcribe. ALL OUTPUT IN ENGLISH. Rules:\n"
    "- A skill is a REUSABLE competence applicable to other similar tasks, NOT a replay of this run. Decide "
    "how many skills this trajectory contains (usually 1, sometimes a few) and return each.\n"
    "- MILD ABSTRACTION: keep the concrete procedure and its UI targets, but replace task-specific VALUES "
    "(filenames, typed text, search terms, specific names) with {parameter} slots; list them in 'parameters'.\n"
    "- Keep ONLY essential steps; DROP glue / navigation / backtracking. One step = one action; you MAY drop "
    "steps. Each skill step MUST reference its 'source_step' index.\n"
    "- Per step: needs_anchor (true if the target is a specific on-screen element that must be seen to locate, "
    "e.g. an icon / menu item / small control; false for keyboard actions or obvious / unique / large targets); "
    "needs_verify (true only for a meaningful, checkable state change) + a short 'verify_cue'.\n"
    "- intent = the step's purpose; target = concise semantic description (NO coordinates).\n"
    'Return ONLY JSON {"skills":[{"name":"snake_case_verb_phrase","description":"...","domain":"gimp|chrome|'
    'libreoffice_calc|libreoffice_writer|libreoffice_impress|vlc|vs_code|thunderbird|os|multi_apps",'
    '"preconditions":["..."],"parameters":[{"name":"...","example":"..."}],"steps":[{"source_step":0,'
    '"intent":"...","target":"...","needs_anchor":true,"needs_verify":false,"verify_cue":""}]}]}'
)


def distill(task: str, enriched: List[Dict[str, Any]], cfg: T2SConfig) -> List[Dict[str, Any]]:
    lines = [f"[step {e['index']}] verb={e['verb']} value={e['value']!r} | target: {e['target'][:120]} "
             f"| effect: {e['effect'][:120]}" for e in enriched]
    body = (f"TASK: {task}\n\nTRAJECTORY ({len(enriched)} steps):\n" + "\n".join(lines)
            + "\n\nExtract the reusable skill(s) as JSON.")
    obj = _extract_json(call_gpt([{"role": "system", "content": DISTILL_SYS},
                                  {"role": "user", "content": body}], cfg))
    skills = obj.get("skills", []) if isinstance(obj, dict) else []
    return [s for s in skills if isinstance(s, dict) and s.get("steps")]


# ---------- assemble + write one skill folder ----------

def write_skill(skill: Dict[str, Any], enr_by_idx: Dict[Any, Dict[str, Any]], img_index: Dict[str, str],
                out_dir: str, seq: int, task_id: str) -> bool:
    name = _sanitize(str(skill.get("name", "skill")))
    folder = os.path.join(out_dir, f"{seq:03d}_{name}")
    frames_dir = os.path.join(folder, "frames")
    steps_out: List[Dict[str, Any]] = []
    copies: List[Tuple[str, str]] = []
    for ss in skill.get("steps", []):
        try:
            key: Any = int(ss.get("source_step"))
        except (TypeError, ValueError):
            key = ss.get("source_step")
        e = enr_by_idx.get(key)
        if e is None:
            logger.debug("drop step: unknown source_step %r (task %s)", ss.get("source_step"), task_id[:8])
            continue
        step: Dict[str, Any] = {
            "intent": str(ss.get("intent", "")),
            "action": {"verb": e["verb"], "target": str(ss.get("target") or e["target"]), "value": e["value"]},
        }
        if ss.get("needs_anchor") and e["anchor_bbox"] and e["before_image"] in img_index:
            fn = f"step{e['index']}_anchor.png"
            step["visual_anchor"] = {"frame": f"frames/{fn}", "bbox_norm": e["anchor_bbox"]}
            copies.append((img_index[e["before_image"]], os.path.join(frames_dir, fn)))
        if ss.get("needs_verify") and ss.get("verify_cue"):
            ver: Dict[str, Any] = {"cue": str(ss["verify_cue"])}
            if e["after_image"] and e["after_image"] in img_index:
                fn = f"step{e['index']}_after.png"
                ver["frame"] = f"frames/{fn}"
                ver["bbox_norm"] = e["change_bbox"]
                copies.append((img_index[e["after_image"]], os.path.join(frames_dir, fn)))
            step["verification"] = ver
        steps_out.append(step)
    if not steps_out:
        return False
    os.makedirs(frames_dir, exist_ok=True)
    for src, dst in copies:
        shutil.copyfile(src, dst)
    doc = {
        "name": name,
        "description": str(skill.get("description", "")),
        "domain": str(skill.get("domain", "")),
        "preconditions": [str(p) for p in skill.get("preconditions", []) if isinstance(p, str)],
        "parameters": [p for p in skill.get("parameters", []) if isinstance(p, dict)],
        "steps": steps_out,
        "provenance": {"dataset": "agentnet", "task_id": task_id,
                       "source_steps": [ss.get("source_step") for ss in skill.get("steps", [])]},
    }
    with open(os.path.join(folder, "skill.json"), "w", encoding="utf-8") as fh:
        json.dump(doc, fh, ensure_ascii=False, indent=2)
    return True


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--in", dest="in_path", required=True, help="AgentNet ubuntu jsonl")
    parser.add_argument("--img-dirs", default="batch_imgs,test_imgs", help="comma-separated screenshot dirs")
    parser.add_argument("--out-dir", required=True, help="output dir (one folder per skill)")
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--min-alignment", type=int, default=8)
    parser.add_argument("--temperature", type=float, default=0.4)
    parser.add_argument("--require-images", action="store_true", help="only trajectories with all frames present")
    args = parser.parse_args()

    if args.limit < 1:
        parser.error("--limit must be >= 1")
    if not os.environ.get("OPENAI_BASE_URL") or not os.environ.get("OPENAI_API_KEY"):
        raise SystemExit("set OPENAI_BASE_URL and OPENAI_API_KEY in env")

    cfg = T2SConfig(in_path=args.in_path,
                    img_dirs=tuple(d.strip() for d in args.img_dirs.split(",") if d.strip()),
                    out_dir=args.out_dir, model=os.environ.get("OSWORLD_PROPOSER_MODEL", "gpt-5.5"),
                    temperature=args.temperature, limit=args.limit, min_alignment=args.min_alignment,
                    require_images=args.require_images)

    img_index = find_images(cfg.img_dirs)
    logger.info("indexed %d screenshots from %s", len(img_index), list(cfg.img_dirs))
    try:
        trajs = select(cfg, img_index)
    except FileNotFoundError:
        raise SystemExit(f"input not found: {cfg.in_path}")
    logger.info("selected %d trajectories (completed, alignment>=%d)", len(trajs), cfg.min_alignment)
    os.makedirs(cfg.out_dir, exist_ok=True)

    nskills = 0
    for i, tj in enumerate(trajs):
        try:
            enriched = enrich_traj(tj, img_index, cfg)
            skills = distill(tj["task"], enriched, cfg)
            enr_by_idx = {e["index"]: e for e in enriched}
            written = 0
            for sk in skills:
                if write_skill(sk, enr_by_idx, img_index, cfg.out_dir, nskills + 1, tj["task_id"]):
                    nskills += 1
                    written += 1
        except Exception as e:  # one trajectory must not kill the batch
            logger.error("traj %s failed: %s", tj.get("task_id", "")[:8], e, exc_info=True)
            continue
        logger.info("[%d/%d] %s (%d steps) -> %d skill(s) [total %d]",
                    i + 1, len(trajs), tj["task_id"][:8], len(tj["steps"]), written, nskills)

    logger.info("wrote %d skills -> %s", nskills, cfg.out_dir)


if __name__ == "__main__":
    main()
