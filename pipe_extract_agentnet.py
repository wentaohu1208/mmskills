"""AgentNet(Ubuntu)轨迹 → 三层 skill(b-full v2)。

分工:
  - VLM 语义:event 切分 + 情境层(goal/cues/state) + click 元素命名
  - 脚本:从真实 value.code 生成原始 procedure(真实动作,零猜测)
  - VLM 加工:按 goal 清洗噪声(打错重打/撤销) + 按"灵活度"智能参数化(保留 raw 可追溯)
  - anchor:真实点击点画红点 → VLM 框 → 兜底(含面积上限),严格跟随加工后的 click 步

用法: FRONTIER_KEY=<key> python pipe_extract_agentnet.py <jsonl> <line> <images_dir> <out>
"""
import os, json, base64, sys, shutil, cv2, requests, re

JSONL, LINE, IMGDIR, OUT = sys.argv[1], int(sys.argv[2]), sys.argv[3], sys.argv[4]
KEY = os.environ["FRONTIER_KEY"]
URL = os.environ.get("FRONTIER_URL", "https://api.frontier-intelligence.tech/v1/chat/completions")
RESIZE_W = 1280
FIX_PAD = 0.03      # 兜底固定框半边长
MAX_AREA = 0.25     # anchor 面积上限,超过视为框歪退兜底(W5)
os.makedirs(OUT, exist_ok=True)


def extract_json(txt):
    """剥 markdown 围栏后取最外层 JSON(W4)。"""
    txt = re.sub(r"```(?:json)?", "", txt)
    m = re.search(r"\{.*\}", txt, re.S)
    return json.loads(m.group(0)) if m else None


def call_vlm(content, max_tokens=4000):
    payload = {"model": "gpt-5.5", "messages": [{"role": "user", "content": content}], "max_tokens": max_tokens}
    last = ""
    for attempt in range(3):
        try:
            r = requests.post(URL, headers={"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"},
                              json=payload, timeout=300)
            last = r.json()["choices"][0]["message"]["content"]
            return extract_json(last)
        except Exception as e:
            print(f"  vlm attempt{attempt} fail: {str(e)[:80]} | raw: {last[:100]}")
    return None


def b64(path):
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()


def clamp01(v):
    return min(max(float(v), 0.0), 1.0)


def parse_action(code):
    """pyautogui code → 结构化动作(C1:放宽正则兼容多写法;C2:write 非贪婪)。"""
    code = code.strip()
    m = re.search(r'(doubleClick|rightClick|tripleClick|click)\(\s*(?:x=)?([\d.]+)\s*,\s*(?:y=)?([\d.]+)', code)
    if m:
        return {"type": "click", "kind": m.group(1), "x": float(m.group(2)), "y": float(m.group(3))}
    m = re.search(r"write\(\s*(?:message=)?['\"](.*?)['\"]\s*\)", code, re.S)
    if m:
        return {"type": "type", "text": m.group(1)}
    m = re.search(r"press\(\s*(?:keys=)?\[?\s*['\"](\w+)['\"]", code)
    if m:
        return {"type": "press", "key": m.group(1)}
    m = re.search(r"hotkey\(\s*(?:keys=)?\[?([^\])]+)", code)
    if m:
        keys = re.findall(r"['\"](\w+)['\"]", m.group(1))
        if keys:
            return {"type": "hotkey", "keys": keys}
    m = re.search(r"scroll\(\s*(-?[\d.]+)", code)
    if m:
        return {"type": "scroll", "amount": m.group(1)}
    m = re.search(r'(moveTo|dragTo)\(\s*(?:x=)?([\d.]+)\s*,\s*(?:y=)?([\d.]+)', code)
    if m:
        return {"type": m.group(1), "x": float(m.group(2)), "y": float(m.group(3))}
    if re.search(r"\bwait\(", code):
        return {"type": "wait"}
    if "terminate" in code:
        return {"type": "terminate"}
    return {"type": "other", "raw": code[:80]}


def action_to_step(a, role):
    """结构化动作 → 原始 procedure 字符串(type 保留原文,交 VLM 加工参数化;S2:verb .get)。"""
    t = a["type"]
    if t == "click":
        verb = {"click": "click", "doubleClick": "double_click", "rightClick": "right_click",
                "tripleClick": "triple_click"}.get(a["kind"], "click")
        return f"{verb}({role})"
    if t == "type":
        return f'type("{a["text"]}")'
    if t == "press":
        return f'press({a["key"]})'
    if t == "hotkey":
        return f'hotkey({"+".join(a["keys"])})'
    if t == "scroll":
        return f'scroll({a["amount"]})'
    if t in ("moveTo", "dragTo"):
        return f"{t}({role})"
    if t == "wait":
        return "wait()"
    return None


def action_desc(a):
    t = a["type"]
    if t == "click":
        return f'{a["kind"]} ({a["x"]},{a["y"]})'
    if t == "type":
        return f'type "{a["text"]}"'
    if t == "press":
        return f'press {a["key"]}'
    if t == "hotkey":
        return f'hotkey {"+".join(a["keys"])}'
    if t == "scroll":
        return f'scroll {a["amount"]}'
    if t in ("moveTo", "dragTo"):
        return f'{t} ({a["x"]},{a["y"]})'
    return t


def draw_dot(src, x, y, out):
    """在 (x,y) 画红点(白边)供 VLM 框;C3:imread 失败返回 False。"""
    img = cv2.imread(src)
    if img is None:
        return False
    h, w = img.shape[:2]
    c = (int(clamp01(x) * w), int(clamp01(y) * h))
    cv2.circle(img, c, 11, (0, 0, 255), -1)
    cv2.circle(img, c, 13, (255, 255, 255), 2)
    cv2.imwrite(out, img, [cv2.IMWRITE_JPEG_QUALITY, 88])
    return True


BOX_PROMPT = (
    "图中有一个【红点】,标记了用户刚刚点击的 UI 元素的中心。"
    "请输出【红点所在的那个 UI 元素】的紧致边界框 bbox=[x0,y0,x1,y1](归一化 0~1,贴着该元素边缘,不要把整片区域都框进去)。"
    "只输出 JSON:{\"bbox\":[x0,y0,x1,y1]}。"
)


def vlm_box(marked):
    content = [{"type": "text", "text": BOX_PROMPT},
               {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64(marked)}"}}]
    r = call_vlm(content, 300)
    if r and isinstance(r.get("bbox"), list) and len(r["bbox"]) == 4:
        try:
            return [float(v) for v in r["bbox"]]
        except (ValueError, TypeError):
            return None
    return None


def contains(bbox, x, y):
    x0, y0, x1, y1 = bbox
    return min(x0, x1) <= x <= max(x0, x1) and min(y0, y1) <= y <= max(y0, y1)


def box_area(bbox):
    x0, y0, x1, y1 = bbox
    return abs(x1 - x0) * abs(y1 - y0)


def crop_box(src, bbox, out):
    """C3:imread 守卫;W3:bbox clamp 到 [0,1]。"""
    img = cv2.imread(src)
    if img is None:
        return False
    h, w = img.shape[:2]
    x0, y0, x1, y1 = [clamp01(v) for v in bbox]
    X0, X1 = int(min(x0, x1) * w), int(max(x0, x1) * w)
    Y0, Y1 = int(min(y0, y1) * h), int(max(y0, y1) * h)
    if X1 - X0 < 4 or Y1 - Y0 < 4:
        return False
    cv2.imwrite(out, img[Y0:Y1, X0:X1], [cv2.IMWRITE_JPEG_QUALITY, 92])
    return True


REFINE_PROMPT = (
    "下面是一个 GUI skill 的 goal + 它的【真实操作流程】(每步是真实动作)。请把它加工成【可复用的 skill 模板】,做两件事:\n"
    "1. 清洗:把【打错重打 / 多余 / 撤销(如 ctrl+u 清行后重输同一命令)】这类人类噪声步标 keep=false。\n"
    "2. 智能参数化:假设这个 skill 要复用到【同类的别的任务】,把命令/输入里【会跟着任务变的部分】挖成有语义的占位符"
    "(如 <file>/<path>/<dir>/<query>/<value>),保留不变的命令骨架、固定选项、以及属于本 skill 固定语义的值。"
    "结合 goal 判断灵活度:goal 越通用可变槽位越多;某值若是该 skill 的固定核心则保留。只加工 type 类(输入文本)步,click/press/hotkey 保持原样。\n\n"
    "goal: {goal}\n"
    "procedure:\n{steps}\n\n"
    "对每一步输出 {{\"keep\":true/false, \"template\":\"参数化后的动作字符串(keep=false 可留空)\"}},"
    "顺序与数量必须与输入完全一致。只输出 JSON:{{\"steps\":[...]}}。"
)


def refine_procedure(goal, proc):
    """VLM 加工:清洗噪声 + 按灵活度参数化。返回 (kept, dropped);失败原样返回。"""
    if not proc:
        return proc, []
    steps_txt = "\n".join(f'{i}. {s["action"]}' for i, s in enumerate(proc))
    content = [{"type": "text", "text": REFINE_PROMPT.format(goal=goal, steps=steps_txt)}]
    r = call_vlm(content, 2000)
    judges = r.get("steps") if isinstance(r, dict) else None
    if not isinstance(judges, list) or len(judges) != len(proc):
        print("  refine skipped (bad/none response), keep raw procedure")
        return proc, []
    kept, dropped = [], []
    for s, j in zip(proc, judges):
        if not (isinstance(j, dict) and j.get("keep", True)):
            dropped.append(s)
            continue
        s2 = dict(s)
        tmpl = j.get("template")
        if tmpl and isinstance(tmpl, str):
            s2["action"] = tmpl
        kept.append(s2)
    return kept, dropped


def healthy_range(ev, frames):
    """C5:frame_range 健壮化(类型检查+逆序交换+clamp)。返回 (lo,hi) 或 None。"""
    fr = ev.get("frame_range")
    if not (isinstance(fr, list) and len(fr) == 2 and all(isinstance(v, int) for v in fr)):
        return None
    lo, hi = fr
    if lo > hi:
        lo, hi = hi, lo
    if frames:
        lo, hi = max(lo, min(frames)), min(hi, max(frames))
    return (lo, hi)


SEM_PROMPT = (
    "你是多模态 GUI agent skill 提取器。下面是一段计算机操作的【关键帧序列】,每帧后标注了该帧用户的【真实动作】(已知事实,无需你猜)。"
    "请只做【语义理解】:把帧切成若干 event,为每个 event 写三层 skill 的【情境层】,并给每个 click 动作的【被点元素】起名。\n"
    "⚠️ 不要输出 procedure(流程将由真实动作生成);不要输出任何 bbox/坐标(坐标由真实动作提供)。\n\n"
    "【event 切分准则】判据:只看一帧静态画面能否认出该用哪个 skill。相邻共用界面/连续必然发生→合并;可独立复用→拆开。宁可合并。"
    "frame_range 用【动作帧】闭区间,相邻 event 不重叠,terminate 帧不计入。\n\n"
    "【每个 event 输出】\n"
    " - name:英文 snake_case\n"
    " - frame_range:[起帧, 止帧]\n"
    " - context:goal / cues(整帧场景) / cue_frame(入口帧号=操作前画面) / "
    "state{mode(工具栏模式或null) / precondition(前置状态英文标签数组) / "
    "state_anchor(读状态的局部:{appearance_frame, locator 文字};只给 frame 和文字 locator,不要坐标;无明显状态则 null)}\n"
    " - click_anchors:该 event 内每个 click 动作一项 {frame(click所在帧号), role(英文snake_case被点元素名), locator(文字描述)};无 click 则空数组 []\n\n"
    "只输出严格 JSON:{\"events\":[{\"name\":..,\"frame_range\":[..],\"context\":{\"goal\":..,\"cues\":..,\"cue_frame\":..,"
    "\"state\":{\"mode\":..,\"precondition\":[..],\"state_anchor\":..}},\"click_anchors\":[{\"frame\":..,\"role\":..,\"locator\":..}]}]}\n"
    "不要输出 JSON 以外任何文字。"
)


# ---- 读 traj(W1/W2 防御) ----
td = None
with open(JSONL) as f:
    for i, line in enumerate(f):
        if i == LINE:
            td = json.loads(line); break
if td is None:
    sys.exit(f"line {LINE} not found in {JSONL}")
steps = td.get("traj") or []
fdir = os.path.join(OUT, "frames"); os.makedirs(fdir, exist_ok=True)
frames, actions, raw_codes = {}, {}, {}
for s in steps:
    idx = s.get("index")
    code = (s.get("value") or {}).get("code", "")
    if idx is None or not code:
        continue
    actions[idx] = parse_action(code)
    raw_codes[idx] = code
    imgp = os.path.join(IMGDIR, s.get("image", ""))
    if not os.path.exists(imgp):
        continue
    img = cv2.imread(imgp)
    if img is None:
        continue
    h, w = img.shape[:2]
    img = cv2.resize(img, (RESIZE_W, int(h * RESIZE_W / w)))
    fp = os.path.join(fdir, f"u{idx:02d}.jpg")
    cv2.imwrite(fp, img, [cv2.IMWRITE_JPEG_QUALITY, 88])
    frames[idx] = fp
print(f"task={td.get('task_id', '?')} frames={len(frames)} steps={len(steps)}")

# ---- 第1步:VLM 语义 ----
content = [{"type": "text", "text": SEM_PROMPT}]
for i in sorted(frames):
    content.append({"type": "text", "text": f"[帧{i} 真实动作:{action_desc(actions[i])}]"})
    content.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64(frames[i])}"}})
sem = call_vlm(content, 5000) or {"events": []}
print("events:", len(sem.get("events", [])))

# ---- 第2/3/4步:原始 procedure → VLM 加工 → anchor ----
adir = os.path.join(OUT, "anchors_v3"); os.makedirs(adir, exist_ok=True)
cdir = os.path.join(OUT, "context_v3"); os.makedirs(cdir, exist_ok=True)
mdir = os.path.join(OUT, "marked"); os.makedirs(mdir, exist_ok=True)
out_events, used = [], set()
stat = {"vlm_box": 0, "fallback_vlm_fail": 0, "fallback_box_miss": 0, "fallback_box_toobig": 0, "dropped": 0}
for ei, ev in enumerate(sem.get("events", [])):
    try:
        rng = healthy_range(ev, frames)
        if rng is None:
            print(f"  event {ei} bad frame_range, skip"); continue
        lo, hi = rng
        en = ev.get("name", f"ev{ei}")
        ctx = ev.get("context", {})
        goal = ctx.get("goal", "")
        click_anchors = [ca for ca in ev.get("click_anchors", []) if isinstance(ca, dict)]
        click_roles = {ca["frame"]: ca.get("role", "target") for ca in click_anchors if "frame" in ca}

        # (a) 原始 procedure:真实动作,去重防边界重叠,跳过 terminate
        raw_proc = []
        for idx in range(lo, hi + 1):
            if idx in used or idx not in actions:
                continue
            used.add(idx)
            if actions[idx]["type"] == "terminate":
                continue
            step = action_to_step(actions[idx], click_roles.get(idx, "target"))
            if step:
                raw_proc.append({"action": step, "from_frame": idx, "raw": raw_codes[idx]})

        # (b) VLM 加工:清洗噪声 + 按灵活度参数化
        proc, dropped = refine_procedure(goal, raw_proc)
        stat["dropped"] += len(dropped)

        # (c) context_fullframe(S1 fallback)
        cf = ctx.get("cue_frame")
        if cf not in frames:
            cf = lo if lo in frames else (min(frames) if frames else None)
        if cf in frames:
            shutil.copy(frames[cf], os.path.join(cdir, f"{ei:02d}_{en}.jpg"))

        # (d) anchor:严格跟随加工后 procedure 里的 click 步(C4 一一对应)
        anchors = []
        for s in proc:
            idx = s.get("from_frame")
            if idx not in actions or actions[idx]["type"] != "click":
                continue
            x, y = actions[idx]["x"], actions[idx]["y"]
            if not (0 <= x <= 1 and 0 <= y <= 1):
                continue
            role = click_roles.get(idx, "target")
            marked = os.path.join(mdir, f"{ei:02d}_{en}__{role}.jpg")
            if not draw_dot(frames[idx], x, y, marked):
                continue
            bbox = vlm_box(marked)
            if bbox is None:
                bbox, src = [x - FIX_PAD, y - FIX_PAD, x + FIX_PAD, y + FIX_PAD], "fallback_vlm_fail"
            elif not contains(bbox, x, y):
                bbox, src = [x - FIX_PAD, y - FIX_PAD, x + FIX_PAD, y + FIX_PAD], "fallback_box_miss"
            elif box_area(bbox) > MAX_AREA:
                bbox, src = [x - FIX_PAD, y - FIX_PAD, x + FIX_PAD, y + FIX_PAD], "fallback_box_toobig"
            else:
                src = "vlm_box"
            stat[src] += 1
            crop_box(frames[idx], bbox, os.path.join(adir, f"{ei:02d}_{en}__{role}.jpg"))
            loc = next((ca.get("locator", "") for ca in click_anchors if ca.get("frame") == idx), "")
            anchors.append({"role": role, "appearance_frame": idx, "click_xy": [x, y],
                            "bbox": [round(clamp01(v), 4) for v in bbox], "bbox_source": src, "locator": loc})

        ev_out = {"name": en, "frame_range": [lo, hi],
                  "skill": {"context": ctx, "anchors": anchors, "procedure": proc}}
        if dropped:
            ev_out["dropped_steps"] = dropped
        out_events.append(ev_out)
    except Exception as e:
        print(f"  event {ei} failed: {str(e)[:90]}")
        continue

data = {"events": out_events, "_category": "gui",
        "_source": f"agentnet_ubuntu:{td.get('task_id', '?')}", "_method": "b-full-v2"}
json.dump(data, open(os.path.join(OUT, "skill_v3.json"), "w"), ensure_ascii=False, indent=2)
print(f"DONE: {len(out_events)} events | {stat}")
