# 自探索 → 轨迹库 设计(explore → trajectory library)· v1

> **定位**:让 agent 在 OSWorld 上**自己探索出任务、执行出轨迹**,产出一个「带标签的轨迹库」,供下游合成 skill。
> **本阶段范围**:**只到"探索出轨迹库"**。skill 合成(distill / 聚类 / 多实例归纳 / 接 traj2skill)是**独立下游阶段,本设计不含**。
> **版本**:这套"探索式 rollout"记为 **v1**。脚本 `scripts/osworld_explore_rollout.py`;100 条产物全表见 `doc/explore_lib_tasks_v1.md`。

---

## 1. 核心原则:恒真(correct by construction)

难点从来不是"探索",是"知道对错"。自造任务没有标准答案,正向"先定任务→再判成败"要么靠不可靠的 VLM 判官、要么要给每个任务合成验证器(最难)。本设计**绕开验证**:

> **不"先定任务再检查做没做到";而"先让 agent 做,再按它实际做成了什么来命名任务"。**
> 于是每条轨迹对它自己那个任务**恒真**——任务是从轨迹反推的,不存在"没做到"。

**三个让它成立的性质**:
1. **恒真** —— 反推的任务,轨迹不可能失败。
2. **错也不致命** —— 反推略偏,最坏是"任务描述略不准",而非"把垃圾轨迹标成成功"。
3. **任务天花板 = worker 能力** —— 只会得到"它真做得到的任务",绝不造出做不到的;强 worker(GPT-5.5)→ 任务更有料。

---

## 2. 流程(6 阶段,输入 → 输出)

```
[输入] app(5 选 1)+ 该 app 的种子池
   │
   ▼
① 起始      从种子池抽一份种子 → 上传进 VM → 按 app 打开                → 活 VM + 首屏(带这份数据)
   │        office=open(等文件加载)/ gimp=launch gimp <图>+sleep / vscode=会话重置+开文件
   ▼
② 提目标    GPT-5.5 看首屏(可选:代入 persona;已探目标促多样;已有内容优先操作它) → {goal, category}   ← 发动机,非成败标准
   │
   ▼
③ Rollout   循环:截图→GPT-5.5{thought,action}→env.step                 → 每步{index,thought,action,截图}
   │        DONE 或到 max-steps 停                                        + end_reason
   ▼
④ 连贯门    GPT-5.5 判官(唯一裁判):是否产生"真实、持久的改动           → {coherent:bool, reason}
   │        (内容/结构/配置,点开别处仍在)"?
   ▼
⑤ 反推任务  GPT-5.5:首屏+末屏+动作 → 约束式 achieved_task               → {achieved_task, faithful}
   │        (要什么/结果需满足的约束,不含操作;只写满足的约束)          ← 未来归纳的 key;仅 coherent 才跑
   ▼
⑥ 存库      全留打标签(coherent + incoherent)                          → 一 episode 一目录
   │
   ▼
[产出] 带标签的轨迹库   ← 本阶段终点
```

| 阶段 | 输入 | 输出 | 谁干 |
|---|---|---|---|
| ① 起始 | app + 种子 | 活 VM + 首屏 | DesktopEnv + 按 app 打开 |
| ② 提目标 | 首屏 + app(+可选 persona +已探目标) | `{goal, category}` | GPT-5.5 |
| ③ Rollout | goal + 活 VM | 每步 `{index,thought,action,img}` + `end_reason` | GPT-5.5 + env |
| ④ 连贯门 | 首/末屏 + 动作序列 | `{coherent, reason}` | GPT-5.5 判官(唯一) |
| ⑤ 反推 | 首屏+末屏+动作(+goal hint) | `{achieved_task, faithful}` | GPT-5.5 |
| ⑥ 存库 | 以上全部 | episode 目录 | 落盘 |

---

## 3. episode 目录(库的一条)

格式与 `cua_gym_rollout.py` / `osworld_eval.py` 一致 → 下游适配器两路共用。

```
<app>/<NNN>/
  step_00_before.png … final.png
  traj.jsonl     每步 {index, thought, action, img_before}
  meta.json      {app, seed_id, persona, goal, category, coherent, coherence_reason,
                  achieved_task, faithful, n_steps, end_reason, dir}
```

- `achieved_task` / `category` 是**一等字段**(未来分簇 / 多实例归纳用);`seed_id` / `persona` 记来自哪份种子 / 哪个用户画像。
- **keep-all-tagged**:coherent 与 incoherent 都存;失败/异常 episode 也经统一出口写 meta(不留无标签的孤儿目录)。

---

## 4. 关键决策 & 理由

- **④ 连贯性只由判官定,判据为"正面"** —— 唯一裁判是一次 GPT-5.5:"是否产生了**真实、持久的改动**(内容/结构/配置,点开别处仍在)"。这是**正面定义"什么算干成事"**,不列"选区/开菜单/导航不算"之类黑名单——因而**通用**:选区/高亮是暂时 UI 状态、不持久,天然判 False;换任何 domain 都成立。**不做像素级粗看**(像素差既误杀小编辑、又误放选区高亮,交给懂内容的判官更可靠)。
- **⑤ 反推 = 约束(要什么),不含操作(怎么做)** —— 任务只写"结果需满足的约束"(如"Net Sales 列 = Sales−Returns−Discounts"),**排除**"打开文件/用名称框选区/点 Data 菜单/敲公式"这些操作(那是步骤的事)。**只写真正满足的约束,略去半途而废的部分**(既不吹牛也不叙述半成品)→ 仍忠实(任务是轨迹做成之事的子集),且是一句高层、用户口吻的指令(对齐 OS-Genesis 高层意图 / NNetnav 一句式惯例)。
- **反推器做薄** —— 只输出一句 achieved_task;**参数化 / 起名 / 相位化全交给 traj2skill 的 ② distill**,不重复造轮子。
- **种子:用 `open`(等加载)+ 种子池多样化** —— `launch` 不等,首屏会停在空桌面 → agent 无视种子;`open` 会等文件打开。一个 domain 的轨迹不该全来自一张表,故每 episode 从池里换一份不同种子;**种子多样 ↔ 未来 N→1 归纳**(同一能力 × 不同数据的多实例)天然协同。
- **② persona × 种子 → 多样但接地的 goal(opt-in)** —— 种子决定屏上**有什么材料**(可行、不悬空),persona 决定**谁在看、想拿它干嘛**(同一张表:会计 / 老师 / 小店主想做的事完全不同),goal 从两者交集长出。**只作用于 ② 提目标一处**(prompt 加"代入 persona;不自然就别硬套"),④ 连贯门 / ⑤ 反推**完全不见 persona**——它是纯上游多样性旋钮。`--persona-pool` 为空 = 老 v1 行为(纯增量)。persona 源用 **Persona Hub**(`2406.20094`)轻过滤子集;思路承 **AgentSynth**(`2506.14205`,persona 播任务)/ **NNetnav**(`2410.02907`,persona 播探索),但我们独有 **persona × 真实种子** 的"多样 × 接地"组合。
- **收集与合成彻底解耦** —— 探索器**只产轨迹库,绝不写 skill**。"1 轨→1 skill"还是"N 轨→1 skill"住在下游合成阶段;探索器换合成方式一个字不用改。

---

## 5. 两处 MLLM prompt(草稿)

**② 提目标**:
```
{可选 persona 前缀:你在扮演用户画像 "{persona}"。在它合理适用于屏上内容处代入其偏好;
 若不自然,就退回对内容做一件合理的事——别硬套。}
你看到 Ubuntu app '{app}' 的首屏。提出 ONE 个用户在这里"值得做成"的具体事(探索目标)——
要求:会留下真实、持久的改动(文档内容/对象/设置),用到屏幕上实际存在的材料,GUI 上约 3–10 步能做完。
若屏幕已显示带内容的文档,优先"操作已有内容"(排序/筛选/格式/做图/计算),而不是从零新建文件。
好目标 = 有实质状态改变;避免琐碎:只开关菜单/对话框、纯导航、无效果的单击。
{多样性提示:"挑一个和这些已探索目标都不同的:[...]"}
只回 JSON:{"goal":"...", "category":"<短标签,如 formatting/chart/formula>"}
```

**④ 连贯门判官**(正面判据):
```
给你 agent 在 '{app}' 上一次运行的 首屏、末屏、动作序列。
只按一条正面判据判 COHERENT:它是否对文档/应用产生了 真实、持久 的改动——内容/结构/配置层面、
点开别处也还在的那种(录入或变换数据、算出公式、应用格式、创建对象、改设置、产出文件)。
末态有这种持久改动 → coherent=true;否则 false。不是判"是否完成某任务",只判"有没有真改了东西"。
只回 JSON:{"coherent": true|false, "reason":"..."}
```

**⑤ 反推任务**(约束式):
```
给你 首屏、末屏、动作序列。把这次运行完成的任务写成一句简洁、高层的用户指令。
写成"约束/要求"(结果需满足什么),不写"怎么做":包含结果的内容/结构/值
(如"Net Sales 列 = Sales−Returns−Discounts""按 June 列降序");
排除所有操作(开了什么 app、用哪个菜单/工具、怎么选区、点击/输入/保存机制、单元格坐标)。
只依据 before→after 与动作,别脑补;只写真正满足的约束,略去未完成/放弃的部分(完全不提半成品)。
只回 JSON:{"achieved_task":"...", "faithful": true|false}
```

---

## 6. 配置 & 默认值

| 旋钮 | 默认 | 说明 |
|---|---|---|
| `--app` | 5 选 1:libreoffice_calc / _writer / _impress / gimp / vs_code | 各有 open recipe(`_APP_SPEC`) |
| `--seed-pool` | `seeds/<app>/`(源自 OSWorld cache) | 按扩展名过滤杂项;每 episode 换一份 |
| `--persona-pool` | 空(=无 persona,纯 v1) | 一行一个 persona(Persona Hub 子集,行长截 200);每 episode 取一个(错相步长,避免 persona 序号恒等于种子序号);池大小尽量与种子池互质以增组合覆盖 |
| `--n-episodes` | 20/app | 一 episode = 一次完整探索 = 一条轨迹 |
| `--max-steps` | 30 | 贴近真人一条任务长度;给粗目标留冗余 |
| `--resume` | off | 跳过已完成 episode(失败的 exception/bad_start/no_goal 会重试),长跑断点续跑 |
| worker | GPT-5.5 | OpenAI 兼容端点(`.env`) |
| 环境 | docker VM(provider=docker) | 与 cua_gym_rollout 同 |

**成本**:≈ `2N+4` 次 GPT-5.5 / skill(1 提目标 + N rollout + 1 判官 + 1 反推;下游 enrich N + distill 1)。

---

## 7. 模块边界:新 vs 复用

| 模块 | 新/复用 |
|---|---|
| 探索器 ①②③、连贯门 ④(纯判官)、反推器 ⑤、存库 ⑥ | 🆕 `osworld_explore_rollout.py` |
| ① enrich · ② distill · write_skill | ♻️ traj2skill(**下游,不在本阶段**) |
| episode → traj2skill 适配器 | 🆕(小,**与 CUA-Gym 路线共用**) |

---

## 8. 明确不做(本阶段)

distill、skill 合成、聚类、多实例归纳(⑤ 要素)、traj2skill 对接、验证器合成 —— 全留给独立的"合成阶段"。

---

## 9. 与 CUA-Gym 路线的关系

| | 任务来源 | 对错处理 | 下游 |
|---|---|---|---|
| CUA-Gym(`cua_gym_rollout.py`) | 现成任务(32K,自带 reward.py) | 确定性 reward.py 判成败 | 共用 traj2skill + 适配器 |
| **自探索 v1(本设计)** | **自造(反推)** | **恒真 + 连贯门,无成败判官** | 共用 traj2skill + 适配器 |

---

## 10. 落地状态 & 结果(v1)

全量跑:**5 app × 20 = 100 条,串行 + resume,约 9h20m,磁盘全程稳。**

| app | coherent | 备注 |
|---|---|---|
| vs_code | 20/20 | 满分(设置/代码编辑易做易验) |
| gimp | 19/20 | 图像操作丰富(裁剪/去色/水印/滤镜) |
| libreoffice_calc | 18/20 | 公式/排序/条件格式/图表 |
| libreoffice_writer | 18/20 | 标题/列表/表格/查找替换 |
| libreoffice_impress | 14/20 | 最弱:失败集中在"改文档 Properties 对话框" |
| **合计** | **89/100** | |

- **质量**:全在真实种子数据上操作;反推是清爽约束句、且忠实(只做一半就如实标"仅表头"/"仅第一行");种子多样 → 能力多样。
- 已知边缘:3 条判官判 coherent 但反推说"无连贯编辑/未完成"(impress-0、gimp-2、gimp-8)——判官与反推轻微不一致,可后续收紧。
- **100 条任务全表**(最初目标 → 反推任务,完整中文):`doc/explore_lib_tasks_v1.md`;轨迹库:`/data/hwt/OSWorld/explore_lib/`。
- 另一路 **CUA-Gym** 也端到端验证过(task→rollout→reward.py 判分→打标签,1 道 calc 得 0.7)。
