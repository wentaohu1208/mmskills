"""组织:扫 SRC 下各 task 的 skill_v3.json,按 _category 连续编号,一 event 一文件夹。

用法:  python pipe_organize.py <SRC_DIR> <OUT_DIR>
  SRC_DIR/*/skill_v3.json + context_v3/ + anchors_v3/  ->  OUT_DIR/<category>/NN_name/
    每个 skill 文件夹 = skill.json + context_fullframe.jpg(cue_frame 整帧) + anchors/<role>.jpg(局部)
"""
import os, json, shutil, re, sys, glob

SRC = sys.argv[1]
OUT = sys.argv[2]


def slug(s):
    return re.sub(r"[^\w一-鿿]+", "_", s).strip("_")[:40]


cat_idx = {}
for sj in sorted(glob.glob(f"{SRC}/*/skill_v3.json")):
    data = json.load(open(sj)); td = os.path.dirname(sj)
    cat = data.get("_category", "gui")
    cdir, adir, sdir = f"{td}/context_v3", f"{td}/anchors_v3", f"{td}/state_v3"
    for ei, ev in enumerate(data["events"]):
        cat_idx[cat] = cat_idx.get(cat, 0) + 1
        nn = f"{cat_idx[cat]:02d}"; name = ev.get("name", f"ev{ei}")
        folder = f"{OUT}/{cat}/{nn}_{slug(name)}"
        os.makedirs(f"{folder}/anchors", exist_ok=True)
        json.dump(ev, open(f"{folder}/skill.json", "w"), ensure_ascii=False, indent=2)
        cf = f"{cdir}/{ei:02d}_{name}.jpg"
        if os.path.exists(cf):
            shutil.copy(cf, f"{folder}/context_fullframe.jpg")
        sa = f"{sdir}/{ei:02d}_{name}.jpg"
        if os.path.exists(sa):
            shutil.copy(sa, f"{folder}/state_anchor.jpg")
        for a in ev["skill"]["anchors"]:
            asrc = f"{adir}/{ei:02d}_{name}__{a['role']}.jpg"
            if os.path.exists(asrc):
                shutil.copy(asrc, f"{folder}/anchors/{a['role']}.jpg")
        print(f"{cat}/{nn}: {name[:34]}")
print("organized ->", OUT)
