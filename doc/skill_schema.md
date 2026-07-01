# 多模态 skill 结构设计(暂定 schema)

> **目的**:定义一条「多模态 GUI agent skill」的结构——字段 / 模态 / 粒度。skill = `task → trajectory` 之后要总结出的产物。
> **定位**:procedural memory 的**可读态**(人可读、可编辑、可蒸),**过程 / 子任务级**粒度。
> **范围**:本文只谈"skill 长什么样";原料盘点(374 success / 1050 fail)、judge、文献与 memory 结构调研的背景留底见 `mmskillrl_0627.md`。

---

## 1. 结构总览

```
MultimodalSkill
│
├─ 第一层 · 身份 / 前置  ✅
│   ├─ name            动词短语 · snake_case · 无域前缀        e.g. apply_paragraph_style_and_type
│   ├─ description     一句话「做什么」= 检索键
│   ├─ domain          所属域                                  gimp / libreoffice_writer / …
│   └─ preconditions   跑它需要的前置状态                      e.g. “Writer 已打开空白文档”
│
├─ 第二层 · 过程主体 = 有序 steps[]  ✅   一步一动作;intent 可被相邻步共享   ← skill 核心
│   └─ step_i
│       ├─ intent          只说目的 · 不说做法 · 可跨相邻步共享
│       ├─ action          verb    规范化动词  click / type / hotkey / drag / scroll
│       │                  target  语义描述 · ⚠️ 不放坐标   e.g. “左上角段落样式下拉框”
│       │                  value   输入内容 · 可变量化       e.g. “{text}”
│       ├─ visual_anchor   〖动作前:目标长这样〗可选 · 仅“目标不显然”的步
│       │                  frame_ref  动作前全屏(存指针)
│       │                  bbox_norm  框「目标元素」 [x,y,w,h] ∈ 0~1
│       └─ verification    〖动作后:成功了没〗可选 · 仅“状态跃迁”的步
│                          cue        文字成功判据
│                          frame_ref  动作后全屏(= 下一步截图)
│                          bbox_norm  框「变化区域」 [x,y,w,h] ∈ 0~1
│
└─ 第三层 · 元信息  ⏳ 暂缓
    parameters(变量槽,登记 value 里的 {…}) · provenance(来源轨迹) · links(关联 skill 边)
```

**三条纪律**(贯穿全结构):
- 🚫 **action 不放坐标**——`target` 只用语义词;定位交给「全屏 `frame_ref` + 归一化 `bbox_norm`(0~1,不锁分辨率)」。
- 🖼️ **存全屏、喂 crop**——存储存全屏(信息全);消费默认切 `frame_ref[bbox]` 成 crop,需空间消歧时才喂全屏 + 画出 bbox。
- ✂️ **按需配置,不均匀铺满**——`visual_anchor` 只给"目标不显然"的步,`verification` 只给"有意义状态跃迁"的步。

**已有意识砍掉的字段**:
| 字段 | 原因 |
|---|---|
| `when_to_use` | 与 `description` 重叠(选择靠 description,执行靠 preconditions) |
| `abstraction_level` | 粒度已锁 composite → 全表常量、零信息 |
| `pitfalls`(易错/纠错) | 暂缓(将来用 1050 失败轨迹填,是差异化点) |
| `focus_crop / context_frame / after_crop` | 并入 `frame_ref + bbox_norm` |

---

## 2. 关键决策 & 理由

**定位:走 Family 1(人可读)而非 latent。** 视觉记忆两大家族——①人可读(截图/crop + 文字,MMSkills/GUI-explorer)vs ②学习式连续 latent(Skill-CMIB `z`、CoMEM Q-Former 向量)。选①:可读、可编辑、可被下游蒸;latent 绑编码器、不可读、内化要连编码器一起蒸,是外挂性表示。

**粒度 = 过程/子任务级(composite)。** 别 atomic(单动作)、别整任务;一个 skill = 一段可复用的多步操作模式。

**name 无域前缀。** 撞名靠独立的 `domain` 字段区分,name 保持干净。

**description = 检索键。** 主流系统(Voyager/Cradle/SkillWeaver/ExpeL/LEGOMem)都拿 description 的 embedding 检索 skill。故写法用"任务指令会用的词、说结果/目标",不写过程;"何时用"不掺进来。

**preconditions 只留状态门槛。** 回答"这条 skill 现在跑得起来吗"(匹配当前屏幕),与 description 的"该不该选它"(匹配意图)分工;`when_to_use` 夹在中间、两头重叠,砍。

**坐标不进 skill。** 绝对像素坐标锁分辨率、诱导"照抄坐标";改用「语义 target + 视觉 anchor」。原始 `click(x,y)` 只用来**裁 crop、算 bbox_norm,用完即弃**;保留的是归一化 bbox(0~1),锚位置又不锁布局。附带好处:模型 rollout 的 response 原生就是归一化坐标,`bbox_norm` 直接可得、无需换算。

**存全屏、消费切 crop(存储 ≠ 消费)。** `crop = 全屏[bbox]`,全屏+bbox 是信息超集、能随时切出 crop;反之只存 crop 则永久丢上下文。crop 的两个好处(省 token、防过度锚定)是**消费端**优化,不该提前到存储端做裁剪。截图 rollout 已落盘,skill 存**指针**近乎零成本。

**按需配置(anchor / verify 不铺满)。** 三个理由:①文字已锁死目标时配图=零信息增益;②每步塞图会诱导模型处处依赖像素、过度锚定(红线③、MMSkills gated view-selection);③`verify` 是"进度里程碑",满地里程碑=没有里程碑,且过渡步常无干净判据(继承 P1"只写可核验"精神)。注意:存指针虽便宜,但 `bbox_norm` 要逐步判定、`cue` 要额外跑 VLM 生成,且过度锚定是"喂什么"的问题——故仍需按需。

**step = 一步一动作(strain 1 → 方案 B)。** 一个 intent 若需多个动作(如"设 Heading 1"=开下拉+选项),保持"一步一动作"、让相邻步共享同一 intent(而非 action 塞一小串)。因为 `visual_anchor`/`verification` 本质是"针对某一个动作"的概念——一步一动作时绑定无歧义,且与将来"逐步消费"天然对齐、不用返工;代价仅 intent 少量重复。对照 LiteGUI:每条样本 = 一个原子 Action + 可跨步的 Subtask 标签。

---

## 3. 文献出处

**skill schema 主参考**(字段与模态从这些工作取):

| 简称 | arXiv | 借鉴到本 schema 的点 |
|---|---|---|
| MMSkills | 2605.13527 | procedure + state cards(when/verify)+ 关键帧;"图是参照非坐标";gated view-selection |
| Skill-DisCo | 2606.26669 | 字段最全对照(name/params/pre-post/…),做 checklist |
| AWM | 2409.07429 | `value` 变量化 → 一条 skill 复用多任务 |
| GUI-explorer | 2505.16827 | 元素 crop → 功能,视觉锚定到元素粒度 |
| Vision-OPD | 2605.18740 | 红点/crop 式聚焦(anchor 当注意力引导,非模板) |
| Skill-SD | 2604.10674 | `golden_workflow` / `mistake_analysis`(后者留给暂缓的 pitfalls) |
| LiteGUI | 2605.07505 | 每步 `{Reason, Subtasks, Action}` → strain 1 的 B 方案对照 |

**memory 结构调研(2025→2026.6,4 片)可迁移范式** —— 主要供将来 skill **bank**(第三层 links + 生命周期)取用,当前 schema 暂未启用:
- 生命周期动词统一为 `写入→存储→检索→反思/巩固→遗忘/淘汰`(各家分型收敛)。
- A-MEM(2502.12110):atomic note = `{content, keywords, tags, context, links}` + 链接演化 → 关联 skill 的字段模板。
- SkillGraph(2605.12039):`prerequisite / enhancement / co-occurrence` 有向边 + 子图检索 → `links` 蓝本。
- Mem0(2504.19413):入库前 `ADD/UPDATE/DELETE/NOOP` 去重门。
- MemoryOS(2506.06326):`Heat = 使用+量+时近` 晋升/淘汰;MemoryBank:recall 强化。
- MemOS(2507.03724):MemCube 的 `provenance + version` → 第三层 `provenance`。
