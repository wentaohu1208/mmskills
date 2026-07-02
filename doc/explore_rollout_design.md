# 自探索 → 轨迹库 设计(explore → trajectory library)

> **定位**:让 agent 在 OSWorld 上**自己探索出任务、执行出轨迹**,产出一个「带标签的轨迹库」,供下游合成 skill。
> **本阶段范围**:**只到"探索出轨迹库"**。skill 合成(distill / 聚类 / 多实例归纳 / 接 traj2skill)是**独立的下游阶段,本设计不含**。
> **背景**:与「现成任务 + 确定性验证器」的 CUA-Gym 路线(见 `cua_gym_rollout.py`)并行的第二条任务来源;两条路**共用下游 traj2skill**。

---

## 1. 核心原则:恒真(correct by construction)

难点从来不是"探索",是"知道对错"。自造任务没有标准答案,正向"先定任务→再判成败"要么靠不可靠的 VLM 判官、要么要给每个任务合成验证器(最难)。本设计**绕开验证**:

> **不"先定任务再检查做没做到";而"先让 agent 做,再按它实际做成了什么来命名任务"。**
> 于是每条轨迹对它自己那个任务**恒真**——任务是从轨迹反推的,不存在"没做到"。

**由此"验证"退化成一个极简的门**:不判"做没做到任务 X"(难),只判"有没有发生一件连贯、有意义的事"(易)。

**三个让它成立的性质**:
1. **恒真** —— 反推的任务,轨迹不可能失败。
2. **错也不致命** —— 反推略偏,最坏是"任务描述略不准",而非"把垃圾轨迹标成成功"(正向判官错一次就往库里塞假成功)。
3. **任务天花板 = worker 能力** —— 只会得到"它真做得到的任务",绝不造出做不到的;强 worker(GPT-5.5)→ 任务更有料。

---

## 2. 流程(6 阶段,输入 → 输出)

```
[输入] app 名 + 种子池(seed-pool)
   │
   ▼
① 起始      从 seed-pool 抽一份种子 → 上传进 VM → 打开 app     → 活 VM + 首屏(带这份数据)
   │
   ▼
② 提目标    GPT-5.5 看首屏(+已探目标促多样)                  → {goal, category}   ← 发动机,非成败标准
   │
   ▼
③ Rollout   循环:截图→GPT-5.5{thought,action}→env.step        → 每步{index,thought,action,截图}
   │        DONE 或到 max-steps 停                              + end_reason
   ▼
④ 连贯门    a.便宜:首末有实质变化? app活? 动作≥K?             → {coherent:bool, reason}
   │        b.轻判官(仅过 a 才调):干成连贯非琐碎的事? 是/否
   ▼
⑤ 反推任务  GPT-5.5:首屏+末屏+动作序列(+goal 当 hint)        → {achieved_task, faithful}
   │        忠实描述"实际做成了什么";仅 coherent 才跑            ← 未来归纳的 key
   ▼
⑥ 存库      全留打标签(coherent + incoherent)                 → 一 episode 一目录
   │
   ▼
[产出] 带标签的轨迹库   ← 本阶段终点
```

| 阶段 | 输入 | 输出 | 谁干 |
|---|---|---|---|
| ① 起始 | app + seed-pool | 活 VM + 首屏 | DesktopEnv + 种子上传 |
| ② 提目标 | 首屏 + app(+已探目标) | `{goal, category}` | GPT-5.5 |
| ③ Rollout | goal + 活 VM | 每步 `{index,thought,action,img}` + `end_reason` | GPT-5.5 + env |
| ④ 连贯门 | 首/末屏 + 动作序列 | `{coherent, reason}` | 便宜检查 + 轻 GPT-5.5 |
| ⑤ 反推 | 首屏+末屏+动作(+goal hint) | `{achieved_task, faithful}` | GPT-5.5 |
| ⑥ 存库 | 以上全部 | episode 目录 | 落盘 |

---

## 3. episode 目录(库的一条)

格式与 `cua_gym_rollout.py` / `osworld_eval.py` 一致 → 下游适配器两路共用。

```
<app>/<ep_id>/
  step_00_before.png … final.png
  traj.jsonl     每步 {index, thought, action, img_before}
  meta.json      {app, seed_id, goal, category, coherent, coherence_reason,
                  achieved_task, faithful, n_steps, end_reason}
```

- `achieved_task` / `category` 是**一等字段**(未来分簇 / 多实例归纳用);
- `seed_id` 记来自哪份种子(provenance + 多样性统计)。

---

## 4. 关键决策 & 理由

- **④ 加"轻 MLLM 判官"** —— 便宜检查(状态变了/app 活/动作≥K)先过;过了才调一句 GPT-5.5 "干成连贯非琐碎的事了吗?"。**注意:判"有没有干成事"(易、可靠),不是判"做没做到某任务"(难、不可靠)**。这是价值命门,又不违背"不用成败判官"。
- **⑤ 永远按实际 before→after 反推** —— 目标(goal)只当发动机 / hint,标签时丢掉。这样恒真最干净。
- **反推器故意做薄** —— 只输出一句忠实的 `achieved_task`(instruction)。**参数化 / 起名 / 相位化,traj2skill 的 ② distill 已全包**,不重复造轮子、不两边打架。
- **收集与合成彻底解耦** —— 探索器**只产轨迹库,绝不写 skill**。"1 轨→1 skill"还是"N 轨→1 skill"住在下游合成阶段;探索器换合成方式一个字不用改。
- **种子池 → 多样性** —— 一个 domain 的轨迹**不该全来自一张种子表**。每 episode 从池里抽不同种子(OSWorld cache 本地 calc 就有 97 份真实 .xlsx)。**种子多样 ↔ 未来 N→1 归纳天然协同**:同一能力 × 不同数据的多个实例,正是抽"不变量"最需要的原料。
- **keep-all-tagged** —— coherent 与 incoherent 都存、打标签,只 coherent 往下走;失败/琐碎留作日后分析。

---

## 5. 两处 MLLM prompt(草稿,首批上真实数据再调)

**② 提目标**:
```
你看到 Ubuntu app '{app}' 的首屏。提出 ONE 个用户在这里"值得做成"的具体事(探索目标)——
要求:会留下真实、持久的改动(文档内容/对象/设置),用到屏幕上实际存在的材料,GUI 上约 3–10 步能做完。
好目标 = 有实质状态改变:录入/变换数据、应用格式、造对象(图表/表格/形状)、配置某设置、跑并验证一条命令。
避免琐碎:只开关菜单/对话框、纯导航、无效果的单击。
{多样性提示:"挑一个和这些已探索目标都不同的:[...]"}
只回 JSON:{"goal":"...", "category":"<短标签,如 formatting/chart/formula>"}
```

**⑤ 反推任务**:
```
给你 agent 在 '{app}' 上一次运行的 首屏 与 末屏,以及它执行的动作序列。
描述这次运行**实际完成了什么任务**——只依据 before→after 的可见变化 + 动作,不要脑补。
agent 可能做得比原意图少(或不同)——照它真正做成的写,带上用到的具体值(文件名/输入/选择)。
写成一句"用户可据此复现该结果"的清晰指令。
(提示——它原本想做:'{goal}';仅当 hint,标签按实际结果。)
只回 JSON:{"achieved_task":"...", "faithful": true|false}
```

---

## 6. 配置 & 默认值

| 旋钮 | 默认 | 说明 |
|---|---|---|
| `--app` | libreoffice_calc(首批) | 先单 app 验证链路 |
| `--seed-pool` | OSWorld cache 里该 app 的 .xlsx | 现成 .xlsx,上传+打开即可,不跑脚本、不碰依赖 |
| `--max-steps` | **20** | 贴近真人一条任务长度(AgentNet ~18.6),给 3–10 步粗目标留冗余;与已验证 OSWorld 配置一致 |
| `--n-episodes` | 20(首批) | 一个 episode = 一次完整探索 = 一条轨迹 |
| worker | GPT-5.5 | OpenAI 兼容端点(`.env`) |
| 环境 | docker VM(已就绪) | 与 cua_gym_rollout 同 |
| 连贯门阈值 | 暂定:≥2 个实质动作(非纯导航)且末屏与首屏有非平凡像素差;过此再调轻判官 | 调门松紧 = 调库质量,首批上数据后再定 |

**脚本**:`osworld_explore_rollout.py`(全新写、不套 PEEU;仅借用 DesktopEnv/step 等通用 OSWorld 接口惯例)。
**成本**:≈ `2N+4` 次 GPT-5.5 / skill(1 提目标 + N rollout + 1 连贯 + 1 反推;下游 enrich N + distill 1)。

---

## 7. 模块边界:新 vs 复用

| 模块 | 新/复用 |
|---|---|
| 探索器 ①②③ | 🆕 |
| 连贯门 ④ | 🆕(轻) |
| 反推器 ⑤ | 🆕 |
| 存库 ⑥ | 🆕(落盘) |
| ① enrich · ② distill · write_skill | ♻️ traj2skill(**下游,不在本阶段**) |
| episode → traj2skill 适配器 | 🆕(小,**两路共用**) |

---

## 8. 明确不做(本阶段)

distill、skill 合成、聚类、多实例归纳(⑤ 要素)、traj2skill 对接、验证器合成 —— 全留给独立的"合成阶段"。

---

## 9. 与 CUA-Gym 路线的关系

| | 任务来源 | 对错处理 | 下游 |
|---|---|---|---|
| CUA-Gym(`cua_gym_rollout.py`,已跑通) | 现成任务 | 确定性 reward.py 判成败 | 共用 traj2skill + 适配器 |
| **自探索(本设计)** | **自造(反推)** | **恒真 + 连贯门,无成败判官** | 共用 traj2skill + 适配器 |
