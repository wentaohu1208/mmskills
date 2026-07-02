# 多模态 skill 结构设计(v3 · 相位化)

> **目的**:定义一条「多模态 GUI agent skill」的结构,并给出从轨迹提炼 skill 的管线(`traj → skill`)。
> **定位**:skill = procedural memory 的**可读态**(人可读、可编辑),**相位级**粒度(不是原子动作、也不是整任务)。
> **范围**:本文只谈"skill 长什么样 + 怎么从轨迹提炼";**OPD 内化机制这一阶段先放一放**。背景原料/文献留底见 `mmskillrl_0627.md`。
> **演进**:早期版是"每步一原子动作 + 每步 bbox"——太像清洗过的轨迹;v3 升级为**相位化 + 去坐标 + 值参数化**(见 §4 为什么)。

---

## 1. 管线总览(traj → skill)

```
输入:最基本的 rollout traj(真实场景底线)
  task 指令  +  每步{ 截图 , 动作(verb, 归一化坐标, value) }
        │
 ① ENRICH      逐步 · MLLM + vision   ← 唯一用 vision 处
   看[前截图 + 后截图 + 动作] → 每步:target(语义) / effect(变了啥)
                                / anchor_bbox(框目标) / change_bbox(变化区域,可空)
        │  enriched steps(把像素→文字 + 框)
 ② DISTILL     整条 · MLLM · 纯文本   ← 不看图
   读 task + enriched steps → 识别可复用 skill(自定几个)
   把连续原子步「升层」成 3–6 个 phase;初步值→{slot};丢胶水步
        │  skill 草稿(相位化,文本里可能还残留具体值)
 ③ SLOT-VERIFY 逐 skill · MLLM · 纯文本 ← 语义去实例化(替代旧的确定性替换)
   拿 parameters + 全部文本字段 → 把漏掉的字面值语义化替成 {slot}
   (只替独立 token,绝不误伤 "desktop"/"formatting";失败回退原文)
        │
 write_skill:用 bbox 把框画到截图上存图(坐标画完即弃、不进 JSON);一 skill 一文件夹
        │
输出:一 skill 一文件夹
```

- **源**:AgentNet(`xlangai/AgentNet` Ubuntu 人类轨迹),**当"最基本裸 traj"用——只取 image + code(截图+动作),丢弃其 thought/reflection 等事后标注**(见 §5)。
- **脚本**:`scripts/agentnet_traj2skill.py`。

---

## 2. skill 结构(v3 schema)

**一 skill 一文件夹**:
```
NNN_<name>/
  skill.json
  frames/          每 phase:1 张 anchor 画框图 + 1 张 verify 画框图
```

`skill.json`:
```json
{
  "name": "set_vscode_dropdown_setting",
  "description": "…(值处用 {slot})",
  "domain": "vs_code",
  "preconditions": ["…"],
  "parameters": [{"name":"setting","example":"Word Wrap"}, {"name":"value","example":"on"}],
  "phases": [
    { "name":"open_settings_page",
      "trigger":"VS Code is open and the Settings tab is not yet open",   // 整屏局面(动作前)
      "action":"Open the Settings UI",                                    // 粗动作(带 {slot})
      "visual_anchor":{"frame":"frames/phase1_anchor.png","object":"the Settings menu item"},  // 画了框的图 + 对象描述,无坐标
      "verification":{"cue":"The Settings tab is open","frame":"frames/phase1_after.png"} },
    { "name":"set_the_value",
      "trigger":"The target setting row is visible",
      "action":"Set {setting} to {value} via its dropdown",
      "visual_anchor":{"frame":"frames/phase2_anchor.png","object":"the setting's dropdown control"},
      "verification":{"cue":"The setting shows {value}","frame":"frames/phase2_after.png"} }
  ],
  "provenance": {"dataset":"agentnet","task_id":"…","phase_source_steps":[[0,1,2],[3,4,5,6]]}
}
```

**每个 phase = 四件套**:
- `trigger` — 这一阶段**开始时整屏的局面**(是"状态/情境",不是某个元素);
- `action` — 这一阶段**一个粗动作**的自然语言(值用 `{slot}`),不是单次点击;
- `visual_anchor` `{frame, object}` — **画了框的截图 + 对象描述**;可选(键盘/无明显目标的阶段没有);**无数字坐标**;
- `verification` `{cue, frame}` — 成功判据(带 slot)+ 动作后的画框图;`bbox` 不出现在 JSON(变化区域框直接画在图上)。

---

## 3. 三条原则

- **① 升层**:phase 而非原子步——一个 phase = "要完成的一件事"(把同子目标的连续点击折进去)。典型 3–6 个 phase,而非 15–27 个点击。
- **② 去坐标**:坐标只是"这一次的位置"、不可迁移;可复用的是"长啥样/是什么"。所以**用 bbox 把框画到截图上,JSON 只留 `{frame, object}`,不存数字坐标**。
- **② 值 → slot**:任务专属的具体值(文件名/输入/搜索词)在 `action/trigger/verify_cue/object/description` 里**全部替换成 `{参数}`**(LLM 语义校验:slot_verify)。

---

## 4. 为什么是 skill 不是 trajectory(5 要素 + 进度)

skill = 从(多次)具体执行里抽象出的**不变、可复用能力**;trajectory = 某一次的记录。差别 = **抽象:从一个实例升到一类事**。参照 MMSkills(`2605.13527`),skill 靠 5 件事:

| 要素 | 含义 | 我们(v3) |
|---|---|---|
| ① 抽象层级 | 停在子目标(相),不在原子点击 | ✅ 升层成 phase |
| ② 去实例化 | 扔掉这一次的坐标/字面值 | ✅ 去坐标 + 值→slot |
| ③ 适用性知识 | 何时用/何时别用(trigger、when_not) | ◻ 有 trigger/precondition,缺 when_not |
| ④ 成败+失败知识 | 怎么算成 + 常见错法/恢复 | ◻ 有 verify,缺失败模式 |
| ⑤ 多实例归纳 | 从同一能力的**多条轨迹**归纳 | ✗ 目前 1 轨迹 1 skill |

**根因**:①–④ 大多是 ⑤ 的结果——**真正的不变量必须多实例才有**;单轨迹只能"清洗+猜"。v3 解决了能从单轨迹做的 **①②**;**③④⑤ 留待"多轨迹归纳"那一轮**(③④ 可部分由强 LLM 补,⑤ 是根本一步)。

---

## 5. 关键决策 & 理由

- **AgentNet 当"裸 traj"用**:真实 rollout 的底线只有**截图 + 执行动作**;AgentNet 的 `thought/reflection/分数/actual_task` 都是**事后 Claude 标注**(源码级证据见 OpenCUA `2508.09123`)。只取 image+code → 贴近真实、且"少→多"可扩展。
- **为何要 ① enrich**:裸 rollout 没有语义;要 target/effect/框,得**扫前后帧现生成**(等价于 AgentNet 的标注层、PEEU 的 M3)。这是真实 rollout 场景的必备前置件。
- **为何相位化(①)**:实测我们的原子步版 15–27 步、太像回放;MMSkills 的 skill 是 **3–6 个相**(trigger→action→verify),≈5× 凝练且是质变。
- **为何画框存图、不存坐标(②)**:坐标是 instance-specific,复用会翻车;框画进图 = 视觉参照"操作这类东西",不泄露坐标。
- **1 轨迹 1 skill(暂)**:多轨迹合并是 ⑤,更大工程,单独一轮。

---

## 6. 文献出处

| 简称 | arXiv | 角色 |
|---|---|---|
| MMSkills | 2605.13527 | skill 结构主参考(procedure + state cards + keyframes);相位化/去坐标灵感 |
| AWM | 2409.07429 | 值变量化(参数槽)|
| Skill-SD | 2604.10674 | 轨迹→golden_workflow 的提炼 pipeline |
| OpenCUA / AgentNet | 2508.09123 | 我们的 skill 源(Ubuntu 人类轨迹);其富字段=事后标注的源码级证据 |
| OSWorld | 2404.07972 | 环境/评测(v1);轨迹容器格式同源 |
| OSWorld 2.0 | 2606.29537 | 长程多应用工作流基准——skill 组合的舞台 |
