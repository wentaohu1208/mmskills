"""AgentNet trajectory -> multimodal skill (traj2skill).

Treat AgentNet as a MINIMAL rollout trajectory: use ONLY the per-step screenshot and
the executed action (verb + normalized coords + value); IGNORE its rich human/model
annotations (thought, reflection, quality flags). This matches what a real agent
rollout actually gives you, and makes it easy to feed richer fields later (few -> many).

Three stages:
  (1) ENRICH  per step, MLLM + vision (the ONLY vision stage). From [before frame,
      after frame, action] -> {target (semantic), effect, anchor_bbox (tight box on the
      target on the BEFORE frame; pointer actions only), change_bbox (changed region on
      the AFTER frame; null if diffuse)}. Turns raw pixels+coords into text + boxes.
  (2) DISTILL  whole trajectory, MLLM, TEXT-ONLY (no vision). From task + enriched steps
      -> reusable multimodal skill(s): the model decides how many, applies mild
      abstraction (values -> {parameters}), drops glue steps, sets per-step intent /
      needs_anchor / verification.
  (3) SLOT-VERIFY  per skill, MLLM, TEXT-ONLY. Replace any leftover instance-specific
      literal with its {parameter} slot SEMANTICALLY (no blind substring substitution, so
      'desktop' is never mangled into 'desk{top}'). Replaces the old rule-based pass.

Output: one FOLDER per skill -- <NNN>_<name>/skill.json + frames/ (full screenshots).
All skill content is ENGLISH.

Endpoint from env: OPENAI_BASE_URL, OPENAI_API_KEY, OSWORLD_PROPOSER_MODEL (gpt-5.5).

Run:
  python agentnet_traj2skill.py --in agentnet_ubuntu_5k.jsonl \
      --img-dirs batch_imgs,test_imgs --out-dir outputs/agentnet_skills_v3 --limit 20
  # repair existing skills in place (re-run only stage 3, no enrich/distill):
  python agentnet_traj2skill.py --out-dir outputs/agentnet_skills_v3 --repair
"""

from __future__ import annotations

import argparse
import base64
import copy
import glob
import json
import logging
import os
import re
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import requests
from PIL import Image, ImageDraw

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
    x = y = None
    if verb in _POINTER:  # coords only matter for pointer actions
        xm = re.search(rf"x\s*=\s*({_NUM})", args)
        ym = re.search(rf"y\s*=\s*({_NUM})", args)
        if xm is None and ym is None:
            pos = re.findall(_NUM, args)  # positional: click(0.018, 0.508)
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


def _to_int(v: Any) -> Any:
    if isinstance(v, list) and len(v) == 1:
        v = v[0]
    try:
        return int(v)
    except (TypeError, ValueError):
        return None  # unhashable/garbage -> a guaranteed enr_by_idx.get() miss, not a crash


_BOX_ANCHOR = (255, 0, 0)
_BOX_CHANGE = (0, 180, 0)


def _save_boxed(src_path: str, bbox: Optional[List[float]], dst_path: str,
                color: Tuple[int, int, int]) -> bool:
    """Save src frame to dst, drawing a colored box (normalized bbox) on it when bbox is given.

    The coordinate is consumed to draw the visual mark and never stored in the skill JSON.
    """
    try:
        im = Image.open(src_path).convert("RGB")
    except (OSError, ValueError):
        return False
    if isinstance(bbox, list) and len(bbox) == 4:
        try:
            w, h = im.size
            x0, y0 = bbox[0] * w, bbox[1] * h
            x1, y1 = (bbox[0] + bbox[2]) * w, (bbox[1] + bbox[3]) * h
            pts = [min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)]  # normalize inverted/degenerate box
            ImageDraw.Draw(im).rectangle(pts, outline=color, width=5)
        except (ValueError, TypeError):
            pass  # degenerate box -> save the frame without the mark
    try:
        os.makedirs(os.path.dirname(dst_path) or ".", exist_ok=True)
        im.save(dst_path)
    except OSError:
        return False
    return True


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
    """Keep ONLY {index, image, code} per step -- treat as a bare rollout.

    `index` is the enumerate position (0..n-1), not AgentNet's field, so the distiller's
    source_step values map back reliably regardless of the source schema.
    """
    steps = [{"index": i, "image": st.get("image", ""),
              "code": st.get("value", {}).get("code", "")} for i, st in enumerate(rec.get("traj", []))]
    return {"task_id": rec.get("task_id", ""),
            "task": rec.get("actual_task") or rec.get("natural_language_task") or rec.get("instruction", ""),
            "steps": steps}


def select(cfg: T2SConfig, img_index: Dict[str, str]) -> List[Dict[str, Any]]:
    """Pick up to `limit` completed, high-alignment trajectories (optionally all-frames-present)."""
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
    """MLLM+vision over (before, after, action) -> {target, effect, anchor_bbox, change_bbox}."""
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
    """Enrich every step. before = step i's frame, after = step i+1's frame (last step: no after)."""
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
    "SKILL(S) this trajectory demonstrates and CONDENSE each into a few high-level PHASES -- do NOT output "
    "one phase per click. ALL OUTPUT IN ENGLISH. Rules:\n"
    "- A skill is a REUSABLE competence applicable to other similar tasks, NOT a replay. Decide how many "
    "skills this trajectory contains (usually 1, sometimes a few) and return each.\n"
    "- GROUP consecutive atomic steps that serve ONE sub-goal into a single PHASE. A typical skill has 3-6 "
    "phases (e.g. 'open the settings page', 'find the target setting', 'set its value'), NOT 15 clicks. Drop "
    "glue / navigation / backtracking steps entirely.\n"
    "- MILD ABSTRACTION: replace task-specific VALUES (filenames, typed text, search terms, specific names) "
    "with {parameter} slots. USE the {slot} INSIDE each phase's 'action' and 'verify_cue' text -- never leave "
    "a literal task-specific value there. List every slot in 'parameters' with an 'example'.\n"
    "- Each phase has:\n"
    "    name         : snake_case phase name\n"
    "    trigger      : the whole-screen STATE at the START of this phase (a situation, not an element)\n"
    "    action       : ONE coarse natural-language action for the whole phase (with {slots}), not a click\n"
    "    source_steps : list of atomic step indices this phase covers\n"
    "    anchor_step  : the ONE atomic step index whose click best represents this phase's key element "
    "(null for keyboard-only phases with no on-screen target)\n"
    "    verify_step  : the atomic step index whose result marks the phase done (usually the last one)\n"
    "    verify_cue   : how to know the phase succeeded (with {slots})\n"
    'Return ONLY JSON {"skills":[{"name":"snake_case_verb_phrase","description":"...","domain":"gimp|chrome|'
    'libreoffice_calc|libreoffice_writer|libreoffice_impress|vlc|vs_code|thunderbird|os|multi_apps",'
    '"preconditions":["..."],"parameters":[{"name":"...","example":"..."}],"phases":[{"name":"...",'
    '"trigger":"...","action":"...","source_steps":[0,1],"anchor_step":1,"verify_step":1,"verify_cue":"..."}]}]}'
)


def distill(task: str, enriched: List[Dict[str, Any]], cfg: T2SConfig) -> List[Dict[str, Any]]:
    """Text-only MLLM over task + enriched steps -> list of reusable skills (model decides count)."""
    lines = [f"[step {e['index']}] verb={e['verb']} value={e['value'][:120]!r} | target: {e['target'][:120]} "
             f"| effect: {e['effect'][:120]}" for e in enriched]
    body = (f"TASK: {task}\n\nTRAJECTORY ({len(enriched)} steps):\n" + "\n".join(lines)
            + "\n\nExtract the reusable skill(s) as JSON.")
    obj = _extract_json(call_gpt([{"role": "system", "content": DISTILL_SYS},
                                  {"role": "user", "content": body}], cfg))
    skills = obj.get("skills", []) if isinstance(obj, dict) else []
    return [s for s in skills if isinstance(s, dict) and s.get("phases")]


# ---------- (3) SLOT-VERIFY: LLM de-instantiation check (replaces rule-based substitution) ----------

SLOT_VERIFY_SYS = (
    "You de-instantiate a GUI skill so it reads generically. You are given the skill's `parameters` (each with a "
    "name and an example value) and a JSON map of text fields (id -> text). Return the SAME map with every "
    "leftover INSTANCE-SPECIFIC literal replaced by its matching {name} slot. RULES:\n"
    "- Replace a value ONLY where it stands as a whole token. NEVER touch a substring inside a larger word: do "
    "NOT turn 'desktop' into 'desk{slot}' when an example is 'top', nor 'formatting' into '{slot}ting' when an "
    "example is 'format'.\n"
    "- Change NOTHING else: keep wording, punctuation, spacing and any EXISTING {slots} identical. Do not "
    "rephrase, translate, summarize, reorder, or add/remove ids.\n"
    "- Only slot a value that is clearly the same instance-specific value a parameter stands for; leave generic "
    "wording alone.\n"
    'Return ONLY JSON with EXACTLY the same ids you were given: {"<id>":"<corrected text>", ...}.'
)


def _skill_text_fields(doc: Dict[str, Any]) -> Dict[str, str]:
    """Collect the slot-bearing text fields of an assembled skill under stable ids."""
    fields: Dict[str, str] = {}
    if isinstance(doc.get("description"), str):
        fields["description"] = doc["description"]
    for i, p in enumerate(doc.get("preconditions", [])):
        if isinstance(p, str):
            fields[f"precondition.{i}"] = p
    for i, ph in enumerate(doc.get("phases", [])):
        if not isinstance(ph, dict):
            continue
        for key in ("trigger", "action"):
            if isinstance(ph.get(key), str):
                fields[f"phase.{i}.{key}"] = ph[key]
        va = ph.get("visual_anchor")
        if isinstance(va, dict) and isinstance(va.get("object"), str):
            fields[f"phase.{i}.object"] = va["object"]
        ver = ph.get("verification")
        if isinstance(ver, dict) and isinstance(ver.get("cue"), str):
            fields[f"phase.{i}.cue"] = ver["cue"]
    return fields


def _set_skill_text_fields(doc: Dict[str, Any], fields: Dict[str, str]) -> None:
    """Write corrected text back into the skill dict by id (only ids we produced)."""
    for fid, txt in fields.items():
        if not isinstance(txt, str):
            continue
        parts = fid.split(".")
        if fid == "description":
            doc["description"] = txt
        elif parts[0] == "precondition":
            idx = int(parts[1])
            if idx < len(doc.get("preconditions", [])):
                doc["preconditions"][idx] = txt
        elif parts[0] == "phase":
            idx, sub = int(parts[1]), parts[2]
            phs = doc.get("phases", [])
            if idx >= len(phs):
                continue
            ph = phs[idx]
            if sub in ("trigger", "action"):
                ph[sub] = txt
            elif sub == "object" and isinstance(ph.get("visual_anchor"), dict):
                ph["visual_anchor"]["object"] = txt
            elif sub == "cue" and isinstance(ph.get("verification"), dict):
                ph["verification"]["cue"] = txt


def slot_verify(doc: Dict[str, Any], cfg: T2SConfig) -> Dict[str, Any]:
    """LLM pass replacing any leftover literal value with its {slot}, semantically (no substring hits).

    Replaces the old rule-based substitution. Returns a corrected COPY; on any failure returns `doc` unchanged.
    """
    params = [p for p in doc.get("parameters", []) if isinstance(p, dict) and p.get("name")]
    fields = _skill_text_fields(doc)
    if not params or not fields:
        return doc
    plist = "\n".join(f"- {{{p['name']}}}  example: {p.get('example', '')!r}" for p in params)
    body = ("PARAMETERS:\n" + plist + "\n\nTEXT FIELDS (id -> text):\n"
            + json.dumps(fields, ensure_ascii=False, indent=2) + "\n\nReturn the corrected map as JSON.")
    try:
        obj = _extract_json(call_gpt([{"role": "system", "content": SLOT_VERIFY_SYS},
                                      {"role": "user", "content": body}], cfg))
    except RuntimeError as e:
        logger.warning("slot_verify failed, keeping draft: %s", e)
        return doc
    if not isinstance(obj, dict):
        return doc
    out = copy.deepcopy(doc)
    _set_skill_text_fields(out, {k: v for k, v in obj.items() if k in fields})
    return out


# ---------- assemble + write one skill folder ----------

def write_skill(skill: Dict[str, Any], enr_by_idx: Dict[Any, Dict[str, Any]], img_index: Dict[str, str],
                out_dir: str, seq: int, task_id: str, cfg: T2SConfig) -> bool:
    """Assemble one distilled skill (phases) into <seq>_<name>/{skill.json, frames/}, drawing the anchor /
    change boxes onto the saved screenshots (no numeric coordinates in the JSON). Text keeps the distiller's
    raw wording; a final `slot_verify` LLM pass replaces any leftover literal with its {slot}. Returns True."""
    name = _sanitize(str(skill.get("name", "skill")))
    folder = os.path.join(out_dir, f"{seq:03d}_{name}")
    frames_dir = os.path.join(folder, "frames")
    params = [p for p in skill.get("parameters", []) if isinstance(p, dict)]
    phases_out: List[Dict[str, Any]] = []
    phase_sources: List[Any] = []
    for i, ph in enumerate(skill.get("phases", [])):
        pnum = i + 1
        phase: Dict[str, Any] = {
            "name": _sanitize(str(ph.get("name", f"phase{pnum}"))),
            "trigger": str(ph.get("trigger", "")),
            "action": str(ph.get("action", "")),
        }
        # anchor: draw the box onto the phase's representative before-frame; store no coordinate
        ea = enr_by_idx.get(_to_int(ph.get("anchor_step")))
        if ea and ea.get("anchor_bbox") and ea["before_image"] in img_index:
            fn = f"phase{pnum}_anchor.png"
            if _save_boxed(img_index[ea["before_image"]], ea["anchor_bbox"],
                           os.path.join(frames_dir, fn), _BOX_ANCHOR):
                phase["visual_anchor"] = {"frame": f"frames/{fn}", "object": str(ea.get("target", ""))}
        # verification: cue + the phase's after-frame (change region boxed if localized)
        ev = enr_by_idx.get(_to_int(ph.get("verify_step")))
        ver: Dict[str, Any] = {"cue": str(ph.get("verify_cue", ""))}
        if ev and ev.get("after_image") and ev["after_image"] in img_index:
            fn = f"phase{pnum}_after.png"
            if _save_boxed(img_index[ev["after_image"]], ev.get("change_bbox"),
                           os.path.join(frames_dir, fn), _BOX_CHANGE):
                ver["frame"] = f"frames/{fn}"
        if ver.get("cue") or ver.get("frame"):
            phase["verification"] = ver
        phases_out.append(phase)
        phase_sources.append(ph.get("source_steps"))
    if not phases_out:
        return False
    os.makedirs(folder, exist_ok=True)
    doc = {
        "name": name,
        "description": str(skill.get("description", "")),
        "domain": str(skill.get("domain", "")),
        "preconditions": [str(p) for p in skill.get("preconditions", []) if isinstance(p, str)],
        "parameters": params,
        "phases": phases_out,
        "provenance": {"dataset": "agentnet", "task_id": task_id, "phase_source_steps": phase_sources},
    }
    doc = slot_verify(doc, cfg)  # (3) LLM de-instantiation: leftover literals -> {slots}
    with open(os.path.join(folder, "skill.json"), "w", encoding="utf-8") as fh:
        json.dump(doc, fh, ensure_ascii=False, indent=2)
    return True


def _repair_existing(cfg: T2SConfig) -> None:
    """Re-run slot_verify over every existing skill.json under cfg.out_dir (no enrich/distill).

    Each file is handled independently (one failure skips only that file) and rewritten ATOMICALLY
    (tmp + os.replace), so a mid-write error can never truncate a previously-good skill.json. Files that
    slot_verify leaves unchanged are not touched at all.
    """
    skill_files = sorted(glob.glob(os.path.join(cfg.out_dir, "*", "skill.json")))
    n = 0
    for sf in skill_files:
        try:
            with open(sf, encoding="utf-8") as fh:
                doc = json.load(fh)
            fixed = slot_verify(doc, cfg)
            if fixed is doc:  # unchanged (no params/fields, API fail, or non-dict reply) -> keep file as-is
                continue
            tmp = sf + ".tmp"
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(fixed, fh, ensure_ascii=False, indent=2)
            os.replace(tmp, sf)  # atomic swap: a failed dump can't leave the original truncated
            n += 1
            logger.info("[repair] %s", os.path.basename(os.path.dirname(sf)))
        except Exception as e:  # one bad file must not abort the repair batch
            logger.error("skip %s: %s", sf, e)
            continue
    logger.info("slot_verify repaired %d skills in %s", n, cfg.out_dir)


def main() -> None:
    """CLI: enrich + distill + slot-verify AgentNet trajectories into per-skill folders.

    With --repair, skip enrich/distill and only re-run slot_verify (stage 3) over existing skill.json.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--in", dest="in_path", default="", help="AgentNet ubuntu jsonl (required unless --repair)")
    parser.add_argument("--img-dirs", default="batch_imgs,test_imgs", help="comma-separated screenshot dirs")
    parser.add_argument("--out-dir", required=True, help="output dir (one folder per skill)")
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--min-alignment", type=int, default=8)
    parser.add_argument("--temperature", type=float, default=0.4)
    parser.add_argument("--require-images", action="store_true", help="only trajectories with all frames present")
    parser.add_argument("--repair", action="store_true",
                        help="re-run slot_verify over existing skill.json in --out-dir (no enrich/distill)")
    args = parser.parse_args()

    if not args.repair and not args.in_path:
        parser.error("--in is required unless --repair")
    if args.limit < 1:
        parser.error("--limit must be >= 1")
    if not os.environ.get("OPENAI_BASE_URL") or not os.environ.get("OPENAI_API_KEY"):
        raise SystemExit("set OPENAI_BASE_URL and OPENAI_API_KEY in env")

    cfg = T2SConfig(in_path=args.in_path,
                    img_dirs=tuple(d.strip() for d in args.img_dirs.split(",") if d.strip()),
                    out_dir=args.out_dir, model=os.environ.get("OSWORLD_PROPOSER_MODEL", "gpt-5.5"),
                    temperature=args.temperature, limit=args.limit, min_alignment=args.min_alignment,
                    require_images=args.require_images)

    if args.repair:
        _repair_existing(cfg)
        return

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
                if write_skill(sk, enr_by_idx, img_index, cfg.out_dir, nskills + 1, tj["task_id"], cfg):
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
