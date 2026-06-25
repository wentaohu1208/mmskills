"""检索/触发 demo(state 版):验证"用情境 state 判触发"。
query = 某 skill 的当前画面整帧;候选 = 各 skill 的 goal + state(mode/precondition 文字 + state_anchor 局部图)。
VLM 判:当前画面满足哪个 skill 的触发态(goal 吻合 + mode/precondition 满足,用 state_anchor 核对)。
用法:  FRONTIER_KEY=<key> python retrieval_demo.py [skill_root=mmskill_example/gui]
"""
import os, sys, json, base64, urllib.request, glob

KEY = os.environ["FRONTIER_KEY"]
URL = "https://api.frontier-intelligence.tech/v1/chat/completions"
ROOT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "mmskill_example", "gui")


def b64(p):
    with open(p, "rb") as f:
        return base64.b64encode(f.read()).decode()


def img_block(p):
    return {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64(p)}"}}


skills = []
for d in sorted(glob.glob(ROOT + "/*")):
    if not os.path.isdir(d):
        continue
    data = json.load(open(d + "/skill.json")); ctx = data["skill"]["context"]; st = ctx.get("state") or {}
    sa_img = f"{d}/state_anchor.jpg"
    skills.append({
        "id": os.path.basename(d)[:2], "name": data["name"], "goal": ctx["goal"],
        "mode": st.get("mode"), "precond": st.get("precondition"),
        "sa_loc": (st.get("state_anchor") or {}).get("locator"),
        "sa_img": sa_img if os.path.exists(sa_img) else None,
        "frame": f"{d}/context_fullframe.jpg",
    })


def call_vlm(content):
    payload = {"model": "gpt-5.5", "messages": [{"role": "user", "content": content}], "max_tokens": 500}
    last = None
    for _ in range(4):  # API 偶发 EOF/抖动,重试
        try:
            req = urllib.request.Request(URL, data=json.dumps(payload).encode(),
                                         headers={"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"})
            return json.load(urllib.request.urlopen(req, timeout=150))["choices"][0]["message"]["content"]
        except Exception as e:
            last = e
    raise last


def parse_json(s):
    s = s.strip(); i, j = s.find("{"), s.rfind("}"); return json.loads(s[i:j + 1])


# 候选目录 + 状态锚点图(有的才喂,图序号在 catalog 里标)
cand_imgs = []
catalog = "候选技能库(GUI):\n"
for s in skills:
    line = f"- skill_{s['id']}: goal={s['goal']} | mode={s['mode']} | precondition={s['precond']}"
    if s["sa_img"]:
        catalog += line + f" | 状态锚点[{s['sa_loc']}](图=第{len(cand_imgs) + 2}张)\n"
        cand_imgs.append(img_block(s["sa_img"]))
    else:
        catalog += line + " | (无状态锚点图)\n"

results = []
for q in skills:
    instr = (f"第1张图=【当前屏幕】。其后是部分技能的【状态锚点局部图】(只用来读状态)。\n{catalog}\n"
             "判断【当前屏幕】此刻正处于哪一个技能的触发时机,依据=① goal 情境是否吻合 ② 当前画面是否满足该技能的 mode 和 precondition"
             "(用其状态锚点局部图/画面去核对,如模式标、页码、是否已选中)。\n"
             "只输出 JSON:{\"skill_id\":\"NN\",\"reason\":\"一句话,点明靠哪个 mode/precondition 判的\"}")
    content = [{"type": "text", "text": instr}, img_block(q["frame"])] + cand_imgs
    try:
        pred = parse_json(call_vlm(content)); pid = str(pred.get("skill_id", "")).replace("skill_", "").zfill(2)
    except Exception as e:
        pred, pid = {"reason": f"ERR:{str(e)[:80]}"}, "??"
    ok = pid == q["id"]
    results.append((q["id"], pid, ok))
    print(f"query={q['id']} {q['name'][:34]:34s} -> {pid} {'OK ' if ok else 'XX '} | {str(pred.get('reason', ''))[:55]}")

acc = sum(r[2] for r in results) / len(results)
print(f"\n=== 触发准确率(state 版): {acc:.0%} ({sum(r[2] for r in results)}/{len(results)}) ===")
print(f"=== 误召回: {[(r[0], r[1]) for r in results if not r[2]] or '无'} ===")
