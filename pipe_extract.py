"""mmskillrl 提取 pipeline v4:纯视频 → gpt-5.5 → 三层 skill(切分准则 + 情境 state)。

用法:  FRONTIER_KEY=<key> python pipe_extract.py <TASK_DIR> [category=gui] [N=16]
  TASK_DIR 下需有 video/video.mp4;产物:skill_v3.json + context_v3/(整帧) + state_v3/(state_anchor) + anchors_v3/。
"""
import os, json, base64, sys, shutil, cv2, requests, re

TASK_DIR = sys.argv[1]
CAT = sys.argv[2] if len(sys.argv) > 2 else "gui"
N = int(sys.argv[3]) if len(sys.argv) > 3 else 16
KEY = os.environ["FRONTIER_KEY"]
URL = "https://api.frontier-intelligence.tech/v1/chat/completions"

# ---- 均匀抽 N 帧 ----
cap = cv2.VideoCapture(os.path.join(TASK_DIR, "video", "video.mp4"))
fps = cap.get(cv2.CAP_PROP_FPS); total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)); dur = total / fps
ts_list = [round(i * dur / (N - 1), 2) for i in range(N)]
fdir = os.path.join(TASK_DIR, "frames_v3"); os.makedirs(fdir, exist_ok=True); frames = {}
for i, ts in enumerate(ts_list):
    fno = max(0, min(int(ts * fps), total - 1)); cap.set(cv2.CAP_PROP_POS_FRAMES, fno); ok, fr = cap.read()
    if not ok:
        continue
    h, w = fr.shape[:2]; fr = cv2.resize(fr, (1280, int(h * 1280.0 / w)))
    fp = os.path.join(fdir, f"u{i:02d}.jpg"); cv2.imwrite(fp, fr, [cv2.IMWRITE_JPEG_QUALITY, 82]); frames[i] = fp
cap.release(); print("frames:", len(frames))

PROMPT = (
"你是多模态 GUI/game agent skill 提取器。下面是从一段操作视频【按时间均匀抽取】的关键帧(每帧前标序号和时间秒)。"
"自己判断 event 边界,为每个 event 提一个三层 skill。每个 event 的 name 用【英文 snake_case】。\n\n"
"【event 切分准则 ★】判据:『只看某一帧静态画面,能不能认出该用这个 skill、而不是下一个?』"
"不能区分(相邻步骤共用界面/对话框、连续必然发生)→【合并成一个 event】(procedure 多步);能区分(可独立复用、画面认得出)→才【拆开】。"
"例:插入对话框【点开→选文件→确认】=一个 event;【翻页】vs【删页】=两个。宁可合并。\n\n"
"【三层 skill】\n"
" - context:goal、cues(整帧整体场景)、cue_frame(入口帧序号=状态刚出现、还没操作那帧)、★state(触发条件):\n"
"     · mode:当前工具栏/编辑模式(如 view_only / select_text / insert_text / annotations);连续动作或游戏导航无明确模式则填 null\n"
"     · precondition:触发本 skill 前画面【必须已满足】的前置状态,简短英文标签数组(GUI 如 on_page_3 / text_selected / dialog_open;游戏如 at_entrance / facing_target / holding_axe 等空间前置)。常等于上一个 event 的结果\n"
"     · state_anchor:画面里【能确认上述状态】的那个局部(★只用来读状态、判时机,≠要操作的元素,不进 procedure)——给 appearance_frame / bbox([x0,y0,x1,y1] 0~1) / locator(如页码框 '3/9'、底部状态栏模式字、模式高亮按钮;游戏里若状态就是世界物体本身则指向它)。若无明显状态指示,state_anchor 填 null\n"
" - anchors:这个 event 里【要操作/对齐的元素】(要点的按钮、要输入的框、要选的项),每个 role/appearance_frame/bbox(紧框)/locator。⚠️只放【手要碰的】;结果/核验归 expect;判状态的局部归 state_anchor,别混进来\n"
" - procedure:有序步骤,每步 action(如 click(role)、input(role,\"值\"))、expect(做对后画面应变成啥=核验)、expect_frame\n\n"
"只输出严格 JSON:{\"events\":[{\"name\":..,\"frame_range\":[起,止],\"skill\":{\"context\":{\"goal\":..,\"cues\":..,\"cue_frame\":..,\"state\":{\"mode\":..,\"precondition\":[..],\"state_anchor\":{\"appearance_frame\":..,\"bbox\":[..],\"locator\":..}}},\"anchors\":[{\"role\":..,\"appearance_frame\":..,\"bbox\":[..],\"locator\":..}],\"procedure\":[{\"action\":..,\"expect\":..,\"expect_frame\":..}]}}]}\n"
"不要输出 JSON 以外任何文字。"
)

content = [{"type": "text", "text": PROMPT}]
for i in sorted(frames):
    b = base64.b64encode(open(frames[i], "rb").read()).decode()
    content.append({"type": "text", "text": f"[帧{i} t={ts_list[i]}s]"})
    content.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b}"}})
payload = {"model": "gpt-5.5", "messages": [{"role": "user", "content": content}], "max_tokens": 4500}

data = None
for attempt in range(3):
    try:
        r = requests.post(URL, headers={"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"},
                          json=payload, timeout=300)
        data = json.loads(re.search(r"\{.*\}", r.json()["choices"][0]["message"]["content"], re.S).group(0)); break
    except Exception as e:
        print(f"  attempt{attempt} fail: {str(e)[:90]}")
if data is None:
    data = {"events": []}
print("events:", len(data.get("events", [])))


def crop_pad(img, bb):
    H, W = img.shape[:2]; x0, y0, x1, y1 = bb
    px, py = max(abs(x1 - x0) * 0.4, 0.025), max(abs(y1 - y0) * 0.4, 0.025)
    X0 = int(max(0.0, min(x0, x1) - px) * W); X1 = int(min(1.0, max(x0, x1) + px) * W)
    Y0 = int(max(0.0, min(y0, y1) - py) * H); Y1 = int(min(1.0, max(y0, y1) + py) * H)
    return img[Y0:Y1, X0:X1] if (X1 - X0 >= 5 and Y1 - Y0 >= 5) else None


adir = os.path.join(TASK_DIR, "anchors_v3"); os.makedirs(adir, exist_ok=True)
cdir = os.path.join(TASK_DIR, "context_v3"); os.makedirs(cdir, exist_ok=True)
sdir = os.path.join(TASK_DIR, "state_v3"); os.makedirs(sdir, exist_ok=True)
ncrop = nstate = 0
for ei, ev in enumerate(data.get("events", [])):
    en = ev.get("name", "ev"); ctx = ev.get("skill", {}).get("context", {})
    cf = ctx.get("cue_frame")
    if cf in frames:
        shutil.copy(frames[cf], os.path.join(cdir, f"{ei:02d}_{en}.jpg"))
    sa = (ctx.get("state") or {}).get("state_anchor")  # state_anchor 裁图(读状态用)
    if isinstance(sa, dict) and sa.get("bbox") and sa.get("appearance_frame") in frames:
        crop = crop_pad(cv2.imread(frames[sa["appearance_frame"]]), sa["bbox"])
        if crop is not None:
            cv2.imwrite(os.path.join(sdir, f"{ei:02d}_{en}.jpg"), crop, [cv2.IMWRITE_JPEG_QUALITY, 92]); nstate += 1
    for a in ev.get("skill", {}).get("anchors", []):  # 操作锚点裁图
        af, bb, role = a.get("appearance_frame"), a.get("bbox"), a.get("role", "?")
        if af not in frames or not bb or len(bb) != 4:
            continue
        crop = crop_pad(cv2.imread(frames[af]), bb)
        if crop is not None:
            cv2.imwrite(os.path.join(adir, f"{ei:02d}_{en}__{role}.jpg"), crop, [cv2.IMWRITE_JPEG_QUALITY, 92]); ncrop += 1
data["_category"] = CAT
json.dump(data, open(os.path.join(TASK_DIR, "skill_v3.json"), "w"), ensure_ascii=False, indent=2)
print(f"DONE: {len(data.get('events', []))} events, {ncrop} anchors, {nstate} state_anchors")
