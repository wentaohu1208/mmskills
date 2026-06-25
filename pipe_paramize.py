"""规则后处理(纯正则,零 LLM):把 procedure 里 input/type/select 等动作的字面取值替换成占位符。
只动 action 的取值参数,绝不碰 expect/locator 里的描述性文字。落地 CLAUDE.md §2 规则④。

用法:  python pipe_paramize.py <SKILL_ROOT>   (递归找 SKILL_ROOT 下所有 skill.json)
"""
import os, json, glob, re, sys

ROOT = sys.argv[1]
# verb(role, "字面值")  ->  verb(role, <占位符>)
PAT = re.compile(r'(input|type|select|fill|enter|set_text|choose)\(([^,)]+),\s*"[^"]*"\)')


def repl(m):
    v, r = m.group(1), m.group(2)
    return f'{v}({r},{"<option>" if v in ("select", "choose") else "<text>"})'


n = 0
for sj in sorted(glob.glob(f"{ROOT}/**/skill.json", recursive=True)):
    data = json.load(open(sj)); ch = False
    for s in data.get("skill", {}).get("procedure", []):
        nw = PAT.sub(repl, s["action"])
        if nw != s["action"]:
            print(f"  {os.path.basename(os.path.dirname(sj))}: {s['action']}  ->  {nw}")
            s["action"] = nw; ch = True; n += 1
    if ch:
        json.dump(data, open(sj, "w"), ensure_ascii=False, indent=2)
print(f"paramize: replaced {n} action value(s) -> placeholder")
