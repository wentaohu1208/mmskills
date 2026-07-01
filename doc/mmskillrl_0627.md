# mmskillrl 讨论记录 · 2026-06-27

> 主题:**设计一种"可被 OPD 蒸入(内化)"的多模态 GUI agent skill**,并把训练/评测范式定下来。
> 本文是讨论结论 + 论文依据的留底。所有论文附 arXiv 链接、**id 均已核实**(方法论 7 篇 pdftotext 硬核 + Skill0/SIRI 经 arXiv API 标题确认);数据集 id 由调研 agent 验证(要严谨可再 pdftotext 核)。

---

## 1. 核心方案:self-OPD 自举闭环

把 **Skill-SD 的自举(rollout→总结 skill)× Vision-OPD/LiteGUI 的视觉特权+单步 OPD** 结合,填一块空地:**没人把"多模态 skill"当 OPD 的蒸馏特权**。

**一句话**:student(VLM GUI agent)自己 rollout → 把成功轨迹总结成多模态 skill → self-OPD:teacher 看 skill、student 看裸图、蒸当前步动作 → 推理撤 skill(内化完成)。

**5 阶段流程**:

```
① ROLLOUT      任务 q → student(裸prompt) → 轨迹 τ=[(s₁,a₁),…,(sₙ,aₙ)]
                                              每步: 截图 sₜ + 真实动作 aₜ(坐标)
        │
② 判成功 ✅    τ → 「这条/这步对吗?」 → 成功轨迹 τ*
   (已落地)     采用 (B)VLM judge + PEEU done 参考对照(见 2026-06-30 节);
                结果 374 success / 1050 capability_fail。备选:(C)动作 vs 标注比对
        │
③ 总结成        τ* → VLM summarizer(从轨迹截图裁锚点/目标)
   多模态 skill      → 过程级 skill(见 §2)
        │
④ self-OPD      对每步 t:
   (单步·offline)  teacher 看[当前截图 sₜ + skill 的相关片段] ← 特权
                   student 看[裸截图 sₜ] → 自采动作 âₜ
                   reverse-KL: âₜ 向 teacher 对齐 → 更新 θ
                   (skill 只喂 teacher;动作不执行、下一步从数据取 → 不在线交互)
        │
⑤ 推理(撤skill)  student 看[裸截图] → 自己输出动作  ✓内化完成
        │
        └─ 内化后 student 更强 ──🔁 回 ① 再 rollout(自举升级)
```

**最小可行第一版(先把🔁拆掉,证明机制)**:

```
高质量多模态 skill(来源待定:三路径之一) ─④─▶ self-OPD 蒸 ─⑤─▶ 撤 skill 测内化
        (先用现成高质量 skill、跳过 ①② 的 self-rollout，先证明"多模态 skill 当特权能蒸进 VLM")
```
跑通后再接 ①②🔁 做成完整自举闭环。

---

## ★ 2026-06-29 实施进展:任务来源(方案 A/B/C)+ rollout + 进度

> §1 的 step ①(任务 + rollout 轨迹)怎么落地。一句话:**任务来源有 A/B/C 三条(GPT 生成 / PEEU / Video2GUI),统一在 OSWorld(docker)上跑;student backbone = Qwen3-VL-8B;先攒数据,再蒸。**

### 角色澄清(重要)
**任务工厂(A 或 B 产"可靠任务 d̃")→ student(8B)在任务上 rollout 产 on-policy 轨迹 → OPD 蒸馏。**
PEEU(方案 B)的探索轨迹只是**副产品**;真正喂训练的是 **8B 自己 rollout 出来的轨迹**(self-OPD 要 on-policy)。

### 方案 A — 启发式 GPT 造任务
- GPT-5.5 当 proposer,看 app 首屏**正向**造 OSWorld 任务 + 自带 setup(能直接跑);对官方 369 Jaccard 去重防泄露。
- 工具 `osworld_task_gen.py`;产出 **795 条文本任务草稿**(`task_drafts_clean.json`)。
- 特点:快、能跑,但任务是 GPT 想象的 → 当补充/冷启动。

### 方案 B — PEEU 复现(探索→反推)⭐ 主线
- 源:**PEEU** `arXiv:2606.27330`(探索→hindsight 反推)。
- 流程:**M1** 看首屏提探索目标 → **M2** GPT-5.5 驱动 pyautogui 探索成轨迹 τ → **M3** 逐步前后截图+a11y diff 抽经验 μ → **M4** 把 μ 聚合反推成**对齐+带约束**的高层任务 d̃。
- 关键:任务从真实探索反推 → **天然对齐、带可验证约束、成功 by construction、免 checker**。
- 工具 `osworld_explorer.py`(M1+M2)+ `osworld_hindsight.py`(M3+M4);**覆盖全 10 OSWorld 域**;任务质量高于 A(过程级多步、约束来自真实观测)。

### 方案 C — Video2GUI(视频→轨迹)
- 源:**Video2GUI** `arXiv:2605.14747`(从无标注互联网视频提 grounded GUI 轨迹)。
- 思路:借其 pipeline——B 轨迹提取(VLM 当标注器,出任务/plan/每步动作 + reason)+ C 三帧 grounding 出坐标 → 得到 (task, trajectory) → 再总结成多模态 skill。
- 特点:不进环境、挖现成视频;⚠️ 视频无真实点击坐标,坐标靠 grounding 反推(小元素准度待实测)。
- 状态:路线既定,pipeline 待跑通。

### 整条 pipeline(B 为主线)
```
任务发现(B:PEEU 探索→反推 / A:GPT 造)──▶ 可靠任务 d̃(带约束)
        │
8B student(general_agent, relative 0–1000 坐标)在任务上 rollout 6 次(成功失败都留)
        │
on-policy 轨迹(截图+动作)──▶ 拆单步 ──▶ OPD 蒸(teacher 看 skill / student 看裸图,reverse-KL)──▶ 蒸进 8B
        │
eval OSWorld 官方 369(撤 skill):基线 8B 10.78% → 目标内化逼近 MMSkills 外挂的 25.40%
```

### 关键决策
- **student backbone = Qwen3-VL-8B**(已有,general_agent 坐标补丁现成,对标 LiteGUI 的 2B-student)。
- **环境/评测 = OSWorld**(docker provider)。**收 skill 在哪 = 测在哪**(跨域内化难)。ScreenSpot/Mind2Web ≠ OSWorld 环境也≠过程 skill,不是主 eval。
- **数据规模标尺**(调研 OPID/LiteGUI/OPSD/OPCD/PEEU):内化方法数据都小(PEEU 2k 轨迹 / LiteGUI 8k 单步样本 / OPCD 几百)。**目标 ~400 任务 × 6 rollout ≈ 2k 轨迹。**
- **OSWorld 10 域**(= MMSkills Table 1):Chrome / GIMP / Calc / Impress / Writer / Multi-app / OS / Mail(=thunderbird)/ VLC / VS Code。

### 进度(2026-06-29)
- ✅ 方案 A:795 文本任务草稿。
- ✅ 方案 B:explorer+hindsight 全建、10 域覆盖、真 VM 端到端验证通过。
- ✅ 任务库 `explore_0629`:**362 任务**(283 done + 79 非done:stuck24/max_steps49/bad_action5/bad_obs1),10 域全覆盖、已完成。
- ✅ 8B rollout(`run.py + GeneralAgent`,student=Qwen3-VL-8B,relative 坐标):6 并行 × 6 轮 = **1827 episode** 已完成(r0-r5)。**配置对齐 OSWorld 官方**(README + run_multienv.py 默认):`--sleep_after_execution 3 --max_steps 15 --max_tokens 1500 --temperature 1.0`(temp 1.0 本就是官方默认;run_multienv 不支持 `--agent_type` 故用 run.py 自己并行)。
- 📊 **轨迹质量基线(8B 弱,实测)**:对齐 + stuck-detection 后 ≈ **真好 69% / 卡死 27% / prose 12%**(prose 集中 chrome ~23%,office/gimp 仅 3–7%)。1398 episode → 预期 **~960 条好轨迹**(够第一次 OPD;PEEU 才 2k)。卡死 = 8B 导航完不知"done"反复点(OSWorld 官方跑弱模型也这样)。**清洗**:过滤 prose-loop(无坐标)+ 折叠重复步,可救回大部分。⚠️ **口径提醒**:69% 指"轨迹可用"(非prose非卡死);按 judge 的"任务真完成"口径,success 仅 **374**(见下方 2026-06-30 节),多数可用轨迹其实是 capability_fail。
- 🛠 工程坑全解:mail(`--profile` 绕 installs.ini hash 不匹配)、multi_apps(开机开文件+上下文提示防路径幻觉)、docker `LOCK_TIMEOUT 10→1200`(并行雪崩)、GeneralAgent `--max_tokens 1500`(默认 32768 撑爆上下文→每步 400)、`--agent_type general`(默认 prompt 报错)、`--sleep_after_execution 3`(不等 UI 刷新→看旧屏)、`lib_run_single` 加 **stuck-detection**(连续 4 次同动作终止)。
- ✅ ② 判成功(judge)已落地并跑完全量(见下方"★ 2026-06-30"节)。
- ⏭ 下一步:③ 生成多模态 skill(先 video2skill,再从 rollout 生成)→ OPD 蒸(teacher 看 skill / student 看裸图,reverse-KL)→ eval OSWorld。

> 代码:`mmskillrl/`(生成器/explorer/hindsight)。数据/服务:远端 `squirrelai-1-a800:/data/hwt/OSWorld`(`explore_*`、`peeu_osworld`、`rollout_8b`、`serve_8b.sh`)。细节见 memory `project_mmskill_osworld_taskgen`。

---

## ★ 2026-06-30 实施进展:② "判成功"(judge)落地 + 全量结果

> §1 的 step ②(判成功,原列为"最硬的坑")怎么落地。**判成功 = (B) VLM judge,且锁定路径二 PEEU**——judge 设计成"对照成功参考轨迹判对错",**只有 PEEU 任务自带 `end_reason==done` 参考**;路径一(正向生成)无参考轨迹、judge 失去基准。

### judge 设计(`osworld_eval.py`)
- **两步**:① 规则预筛(无 VLM:丢损坏——无 traj/无截图/无可解析动作 + 末帧全黑白)→ ② GPT-5.5 三分类 `success / capability_fail / env_fail`(env_fail 丢,后两者留、各带"对错+错在哪"喂 skill 总结)。
- **只对 283 个 `end_reason==done` 参考判**:非 done / md5 对不上 → dropped(`no_done_ref`),不烧 token。
- **帧策略 = 末 5 帧 + 完整动作文字序列**(依调研:outcome judge 主流喂少量末态帧 PAE/OS-Genesis 末3帧、DigiRL 末1帧;"帧多不筛反而变差"有 WebJudge/AgentRewardBench 消融;均匀采样无人用)。
- **可靠性**:抽样 30 条 + 亲自看截图复核 → 可靠,唯一倾向 success 偏宽(意图达成即算成功,容忍无害冗余)。

### 全量结果(1827 episode)
- **judged 1426**:success **374** / capability_fail **1050** / error 2 → 整体 **SR 26.2%**。
- **dropped 401**:no_done_ref 343 + corrupt 56 + env_fail 2。
- **by app(SR 高→低)**:thunderbird 46% / gimp 39% / writer 33% / chrome 29% / vlc 29% / vs_code 26% / os 26% / impress 18% / calc 14% / **multi_apps 1%**(跨应用组合最难,几乎无正样本)。
- **by round**:r0-r5 全在 **23-29%、稳定**(8B 静态不学习、各轮一致 → 数据健康)。
- ★ **关键发现**:VLM judge 捞出 26% success,而 OSWorld 官方 execution evaluator 对这些 PEEU 反推任务给 **0.0 分** → 印证 rule-based 严重低估(AgentRewardBench);**没有 judge 就没有正样本**。
- ⚠️ **正样本量现实**:可作 OPD 正样本的 success 仅 **374**(原按"轨迹可用 69%"估的 ~960 是另一口径);capability_fail 1050 多是"轨迹完整但任务没做成",可作负样本/对比。374 偏少(PEEU 论文 2k)但可先试。
- ⚠️ **后续修正(见下方 2026-07-01 节)**:283 done 经审计含 ~12% 退化任务(P2)+ 27% 约束噪声(P1),清洗后真实正样本更少、需重跑。

> judge 代码 `mmskillrl/osworld_eval.py`;结果 `squirrelai-1-a800:/data/hwt/OSWorld/judged_full.jsonl`+`dropped_full.jsonl`。细节见 memory `project_mmskillrl_judge`。

---

## ★ 2026-07-01:方案 B 任务质量 · 修复的三个 bug(P1/P2/P3)

> 对方案 B 产出的 peeu_task 做体检,定位并修复三个 bug。代码:`osworld_hindsight.py`(M3/M4)、`osworld_explorer.py`(vs_code reset);均已 commit + push + 同步远程,并在真实数据 / VM 上验证修复生效。

### P1 · 约束被观测态污染
- **bug**:M3/M4 提示词把"看到的界面状态"(菜单/下拉框内容、对话框默认值、偶发计数)也当成 `constraints` 抽出来,导致约束里混入非任务要求。
- **修复**:提示词区分"任务要求 vs 观测态"——观测态分流到新字段 `observations`,`constraints` 只留可核验的成功条件;去掉"越严越好"。

### P2 · 退化任务未隔离
- **bug**:以 `end_reason==done` 当正样本,但"报错收尾"(环境无网/无媒体/连不上)和"空操作/否定"(开菜单又关、确认为空、该删没删)的轨迹也混进了正样本池。
- **修复**:M4 增加 `verdict`(clean / degenerate_error / degenerate_noop),`main()` 把退化任务路由到 `*_degenerate.jsonl` 隔离(不删,排除出正样本池)。

### P3 · vs_code reset 状态泄漏
- **bug**:`env.reset` 重启 `code` 时,VS Code 单实例 + 自动恢复上次会话 → reset 只重聚焦旧脏窗口,上一个 goal 的界面状态(如 Settings 页)泄漏进后续 goal 的轨迹。
- **修复**:reset 改为先 `pkill` 杀进程 + 关会话恢复(`window.restoreWindows:none`)+ `--disable-workspace-trust --new-window`。

---

## ★ 机制全程走查:训练 → 推理 → 效果 → 为什么(2026-06-27 定稿)

> 把 §1 方案 + skill 串成一条完整线索,回答"怎么训、训完怎么用、能达到什么、为什么 work"。用"新建文件夹"这个 3 步 skill 贯穿。
> ⚠️ 下面例子里的 skill 字段(`steps / desc / red_dot`…)只是**示意**,**skill 具体结构尚未定**——这里讲的是**机制**,不是结构。

**一句话**:训练时让 teacher 看着 skill 手把手教 student;教完撤掉 skill,student 看裸截图自己就会做——skill 的能力"长进权重",推理零额外开销。

### 1. 训练时(怎么教)

- **数据切成步**:一条"新建文件夹"轨迹(3 步)→ 拆成 3 个训练样本(①点新建图标 / ②输名字 / ③回车);
- **按步投影**:训练到第 t 步,**只**从 skill 取「**全局流程 + steps[t] 这一条**」喂 teacher(不喂别的步,免干扰);
- **一步内两边各看各的**(以第②步"输名字"为例):

  | | 看到什么 | 输出 |
  |---|---|---|
  | **teacher** | 当前截图 + **skill 特权**(流程"现在在第②步" + steps[2] 的 red-dot/crop/理由) | 知道该 `TYPE "data"`,给**准**的动作分布 |
  | **student** | **只有裸截图** | 自己采样动作(可能错) |

- **蒸**:reverse-KL 把 student 的动作往 teacher 拉 → 更新 student 权重;逐步过完整条轨迹、所有轨迹;
- **(可选)课程退火**:后期把 skill 提示(desc/red-dot)**逐步撤掉**,逼 student 越来越靠裸图自己做(Skill0 式);
- 全程:**skill 只喂 teacher,student 始终只看裸截图;动作不执行、下一步从数据取 → 单步、离线、不碰环境**。

### 2. 推理时(训练完怎么用)

```
student 看[ 指令 + 当前裸截图 ] ──▶ 直接输出动作 ──▶ 执行 ──▶ 看新截图 ──▶ 再输出…
  ↑ 无 skill、无 teacher、无 red-dot、无检索注入;一步步走完整个多步任务(end2end)
```

skill **彻底消失**:不查 skill 库、不注入任何东西、不裁 crop;student 凭**裸截图 + 内化进权重的能力**,自己识别"这是命名框 → 该输名字",把任务做完。

### 3. 能达到什么样子(效果)

| | 内化前(裸 student) | 内化后(训练完) |
|---|---|---|
| 看裸命名框 | 不知干嘛 / 点错 | **直接 TYPE 名字** |
| 多步任务 | 走两步就崩 | **走完整条** |
| 推理开销 | — | **零额外**(一次 forward) |
| 小模型 | 吃不动外挂 skill | **2B 也会**(能力在权重,不靠 base 强) |

**端到端**:像 LiteGUI,单步训出的能力在 **OSWorld 真环境**能跑多步任务、成功率涨。

### 4. 为什么这样能 work(4 个原理)

1. **特权信息蒸馏**(根本):teacher 看了 skill → 比裸 student 强;蒸馏**逼 student 在没 skill 时也达到有 skill 的 teacher 水平** → 把"看了 skill 才会的本事"**压进 student 参数**(Vapnik privileged information;Vision-OPD/LiteGUI 都靠它);
2. **on-policy(OPD)> SFT**:student 先**自采**(犯真实的错),teacher 在**它犯错处**纠正 → 治 exposure bias;dense 逐 token 监督,比 RL 稀疏 reward 高效;
3. **撤了 skill 还会(能内化)**:skill 指的东西(图标/框)**画面里本来就有**、student 看裸图**够得着**,red-dot/crop 帮它聚焦,蒸完自己会聚焦 → **信息在画面里才能内化,画面外知识内化不了**(self/同分布,Vision-OPD 已证);
4. **单步训出多步能力**:历史窗口(知道前面干了啥)+ 子任务规划(维护整体进度)+ 过程级 skill(整段流程感)→ 模型学的是"**基于历史和进度,做好当前步**",串起来 = 多步能力(LiteGUI 已证)。

> **总纲**:训练时 teacher 拿 skill 当"特权小抄",在 student 自己写的答案上逐步批改,把"看小抄才会的"蒸进权重;推理时收走小抄,student 看裸截图自己一步步做完多步任务,零额外开销、小模型也行——因为 **skill 指的东西画面里都有,student 被教会了自己看、自己做**。

---

## 3. 关键论文依据(本 session 精读/调研结论)

### 已硬核(pdftotext 确认标题+内容)

- **Vision-OPD** — `Learning to See Fine Details for MLLMs via On-Policy Self-Distillation` · https://arxiv.org/abs/2605.18740
  - teacher 看"当前图裁放大的 crop"(特权)、student 看全图,on-policy 自蒸馏 → 内化"看清细节";
  - 数据集 **Vision-OPD-6K**(HF `yuanqianhao/Vision-OPD-6K`):来自 **V\*** 的 grounding 数据、全图带**红框**、6196 条;
  - ⚠️ **训练评测同源**(都用 V\*,V\* Bench 有泄露嫌疑);**红框只训练有、推理无**(评测 prompt 无红框);训练**单步**;
  - 它蒸"感知/grounding",**不是 skill**(全文 skill=0)。借鉴:视觉特权自蒸馏可内化;坑:别训评同源。

- **LiteGUI** — `Distilling Compact GUI Agents with Reinforcement Learning`(Moore Threads AI)· https://arxiv.org/abs/2605.07505
  - **唯一明确的 GUI agent + OPD**;**Guided-OPD**:teacher 拿"人工核验的正确动作集"当特权(Most-Matched-GT 选最贴 student 的那个),Teacher-forcing Reverse KL;+ Multi-solution Dual-level GRPO;
  - **单步 teacher-forcing 训练、offline、不在线交互**(动作不执行、下一步从数据取);
  - 输出 JSON `{Reason, Subtasks, Action(type, bbox, value)}`,每状态配 **K 个正确动作(多解)**;
  - backbone Qwen3-VL-2B / 30B-A3B,teacher Qwen3-VL-32B;**最多 16×A100**(2B 蒸馏只要 8 卡),1 epoch;
  - 评测 **ScreenSpot-Pro 单步 46.86% + OSWorld 端到端 13.24%(≈2× baseline)**;
  - **数据/代码未公开**(HF/GitHub 搜不到);它蒸**轨迹/动作**,**不是 skill**(skill=0)。借鉴:训练范式可直接照搬;差异化:你蒸 skill 不蒸动作。

- **Skill-SD** — `Skill-Conditioned Self-Distillation for Multi-turn LLM Agents` · https://arxiv.org/abs/2604.10674
  - **skill 来源 = self-bootstrap**:student 裸 prompt 跑出完成轨迹 → 辅助 LLM(实现用字节 **Seed1.8**)总结成 **3 字段 JSON `{success_analysis, mistake_analysis, golden_workflow}`**;冷启动:一开始 bank 空,裸跑出第一批轨迹再总结;
  - skill 只喂 teacher、student 裸 prompt、importance-weighted reverse-KL;纯文本 agent(AppWorld/Sokoban)。借鉴:总结 pipeline 可直接抄来给视频/演示轨迹造 skill。

- **MMSkills** — `Towards Multimodal Skills for General Visual Agents` · https://arxiv.org/abs/2605.13527
  - skill = **text procedure + state cards(何时用/验证线索)+ multi-view keyframes**;**过程级**粒度(一个 skill = 一段可复用动作模式)。我们 §2 的结构主要参考它。
  - ⚠️ **使用方式 = 外挂、不训练**:branch-load 运行时把 skill 证据对齐 **live screen** 注入主 agent;**评测是 end2end** —— OSWorld / macOSWorld / VAB-Minecraft / Super-Mario(真环境跑整条任务)。

- **MMG2Skill** — `Distill In-the-Wild Guides into Self-Evolving Skills` · https://arxiv.org/abs/2606.01993
  - skill = 可编辑 **SKILL.md** = `procedure(ui) + applicability conditions(ci) + expected-state cues(vi) + recovery`;**过程级**,且有 sibling/prerequisite procedures(可组合/层级)。
  - ⚠️ **使用方式 = 外挂、不训练**:闭环 rollout 中条件化 fixed VLM、按轨迹根因修订 skill;**评测 end2end** —— MMG2Skill-Bench(桌面 GUI 控制 / 开放游戏 / 卡牌,交互环境)。

- **Skill-CMIB** — `Multimodal Agent Skill via Conditional Multimodal Information Bottleneck` · https://arxiv.org/abs/2605.08526
  - **外挂**多模态 skill:文字卡 c + 视觉残差 latent z,软前缀注入**冻结** backbone;**没内化**(推理撤前缀就退化);训练评测单步 teacher-forcing。是我们的"起点对照"(外挂 → 我们要内化)。

- **OSWorld**(评测环境)— `Benchmarking Multimodal Agents for Open-Ended Tasks in Real Computer Environments` · https://arxiv.org/abs/2404.07972
  - 真 Ubuntu/Windows 虚拟机,**end2end 在线**跑整条任务、验证最终状态。我们的端到端评测用它。

### ✅ 已核实(arXiv API 标题搜确认 id 正确)

- **SKILL0** — `SKILL0: In-Context Agentic Reinforcement Learning for Skill Internalization` · https://arxiv.org/abs/2604.02268
  - skill 来源对照:**外部给定** skill bank,ICRL + 课程退火逐步撤 skill 内化。
  - (注:另有后续 **Skill0.5** · https://arxiv.org/abs/2605.28424 ——"内化 + 利用 + OOD 泛化",可关注。)
- **SIRI** — `SIRI: Self-Internalizing Reinforcement Learning with Intrinsic Skills for LLM Agent Training` · https://arxiv.org/abs/2606.02355
  - skill 来源对照:策略**自挖**技能,蒸进裸策略。

> skill 来源三条路:**外部给(Skill0)/ 自挖(SIRI)/ 轨迹总结(Skill-SD)**。我们走 **Skill-SD 式(轨迹总结)**,但升级成多模态。

### judge 帧数/方法论调研(2026-06-30,为 ② 判成功定策)
> 调研"如何用 VLM 判 GUI agent 轨迹成功 + 喂多少帧",结论(均抓正文取证):
> - **判定两派**:程序化/execution-based(OSWorld/WebArena/AndroidWorld,读最终系统状态、不看图)vs VLM-as-judge(补程序化的扩展性短板,看截图判)。
> - **outcome judge 喂帧主流 = 少量末态帧**:PAE(`2412.13194`)末3帧、OS-Genesis(`2412.19723`)末3帧、DigiRL(`2406.11896`)末1帧、AgentRewardBench(`2504.08942`)首+末帧。
> - **"帧多不筛反而变差"**:WebJudge(`2504.01382`)消融 δ=2(塞太多帧)一致性反降;AgentRewardBench"更多信息反而干扰 judge"。要兼顾过程则用**关键帧筛选**(相关性打分)而非均匀采样。
> - **rule-based 系统性低估成功率**(AgentRewardBench,WebArena 低 16.7%)→ 印证我们 VLM judge 捞回 26% success(官方给 0.0)。
> → 我们最终选 **末 5 帧 + 完整动作文字**(动作文字补过程),不用均匀采样。

---

## 4. 训练 & 评测范式(调研坐实)

> ⚠️ **先分两类,别混**:
> - **外挂式多模态 skill(MMSkills / MMG2Skill)**:**不训练**(冻结模型),agent 在 **end2end 真环境**(OSWorld / macOSWorld / Minecraft 等)多步 rollout 里**检索注入** skill 来用 —— 它们本来就是 **end2end** 的,不存在"单步训练"这回事;
> - **内化式(LiteGUI / Vision-OPD / Skill-CMIB / 我们的方案)**:**训练**把能力/skill 蒸进权重。**下面"单步训练"只指这一类。**

- **训练**:主流**内化式** GUI agent **几乎全是单步**(静态轨迹 teacher-forcing / grounding),**offline、不在线交互**;在线 RL 训真环境又贵又不稳,极少。→ 你单步训练**完全主流、合法**。
- **评测:双轨都要报**(证据:UI-TARS / OS-Atlas / Aguvis / LiteGUI 全是两类都测):
  - **step-wise**(grounding / 单步动作准确率):**ScreenSpot-Pro** 等;
  - **end2end**(真环境跑整条任务):**OSWorld** 等;
  - 只报 step-wise 会被质疑"回避错误累积"(就是我们批 Vision-OPD 的点);**OSWorld 端到端涨多少是说服力关键**。

```
我们的:
  训练:  单步(skill+OPD,静态轨迹)               ← 主流,无可质疑
  评测:  ① ScreenSpot-Pro (step-wise grounding)
         ② OSWorld (end2end 任务完成)  ← 硬通货,证明"skill 能迁移到完整任务"
```

---

## 5. 数据

> ⚠️ **数据集尚未确定**,以下是候选(先不拍板)。

- **训练源(候选)**:
  - **OS-Atlas**(跨平台含桌面,Apache-2.0 可商用,归一化 bbox,~13M 元素)· https://arxiv.org/abs/2410.23218;
  - **OmniAct**(三桌面 OS 小控件,绝对 bbox,自带 split,可商用)· https://arxiv.org/abs/2402.17553。
- **评测**(与训练源**不重叠**,避 V\* 式同源泄露):
  - **ScreenSpot-Pro**(高分辨率桌面小元素,MIT)· https://arxiv.org/abs/2504.07981;
  - **OSWorld**(端到端)· https://arxiv.org/abs/2404.07972。
- **数据格式参考 LiteGUI**:每步 JSON `{Reason, Subtasks, Action(type, bbox, value)}` + 多解 `valid_actions[K]`;坐标 `[xmin,ymin,xmax,ymax]`。

---

## 6. 关键判断 & 坑

1. **"用 OPD/OPSD 内化多模态 skill" = 蓝海**:2026.1-6 真·GUI agent+OPD 目前只 LiteGUI 最接近,但它蒸**动作**、不蒸 **skill**;Vision-OPD 蒸**感知**、非 agent。**现在多模态 skill 主流是"外挂 + end2end 用"(MMSkills/MMG2Skill 在 OSWorld 等真环境检索注入);把它"内化 + 单步训进权重"没人系统做 —— 这正是我们的差异化空地。**
2. **训练评测必须分开**(V\* 同源泄露的教训):训练源与评测集(ScreenSpot-Pro / OSWorld)必须不重叠。
3. **self-OPD 的"判成功"已落地**(路径二 PEEU + VLM judge,见 2026-06-30 节);起步先用现成高质量 skill(三路径之一)验证机制,完整 self-rollout 自举留作增量。
4. **skill 粒度别再 atomic**:过程/子任务级,训练时投影到单步。
5. **视觉特权 self 同分布可内化**(Vision-OPD 证),跨域复用才难——第一版只做 self/同分布。

---

## 附录:参考文献汇总(17 篇 · id/标题全部硬核)

> 按"在本方案里扮演的角色"分 4 组。**[精读]** = 走过 paper-deep-read / 复现;**[调研]** = survey 抓取。所有标题经 pdftotext 或 arXiv API 核验,id 均已确认正确。

### A. OPD / 自蒸馏方法学(蒸馏 backbone —"怎么蒸")

| 简称 | 标题 | 链接 | 角色 | 状态 |
|---|---|---|---|---|
| **OPSD** | Self-Distilled Reasoner: On-Policy Self-Distillation for Large Language Models | https://arxiv.org/abs/2601.18734 | OPD 系列源头:on-policy 自蒸馏给密集 token 监督 | [精读] |
| **OPCD** | On-Policy Context Distillation for Language Models | https://arxiv.org/abs/2602.12275 | 把"上下文里的知识"蒸进权重 → 撤上下文仍会 | [精读] |
| **OPID** | OPID: On-Policy Skill Distillation for Agentic Reinforcement Learning | https://arxiv.org/abs/2606.26790 | 自举 skill + 在线 RL + 虚拟 teacher 自打分,**最近亲** | [精读] |
| **Vision-OPD** | Learning to See Fine Details for MLLMs via On-Policy Self-Distillation | https://arxiv.org/abs/2605.18740 | 证明视觉特权(crop/红框)可自蒸内化 | [精读] |
| **LiteGUI** | Distilling Compact GUI Agents with Reinforcement Learning | https://arxiv.org/abs/2605.07505 | 唯一 GUI agent + OPD;单步训练范式直接照搬 | [精读] |

### B. 多模态 skill 表示与使用(外挂式 —"skill 长什么样")

| 简称 | 标题 | 链接 | 角色 | 状态 |
|---|---|---|---|---|
| **MMSkills** | Towards Multimodal Skills for General Visual Agents | https://arxiv.org/abs/2605.13527 | 过程级 skill 结构(text procedure + state cards + keyframes)主参考 | [调研] |
| **MMG2Skill** | Distill In-the-Wild Guides into Self-Evolving Skills | https://arxiv.org/abs/2606.01993 | SKILL.md 可编辑 / 可组合 / 含 recovery | [调研] |
| **Skill-CMIB** | Multimodal Agent Skill via Conditional Multimodal Information Bottleneck | https://arxiv.org/abs/2605.08526 | 外挂多模态 skill(软前缀注入冻结 backbone),"起点对照" | [调研] |

### C. skill 内化 / skill 来源(文本 agent —"skill 哪来 + 怎么内化")

| 简称 | 标题 | 链接 | 角色 | 状态 |
|---|---|---|---|---|
| **Skill-SD** | Skill-Conditioned Self-Distillation for Multi-turn LLM Agents | https://arxiv.org/abs/2604.10674 | 自举总结 skill 的 pipeline 来源 | [精读] |
| **Skill0** | SKILL0: In-Context Agentic Reinforcement Learning for Skill Internalization | https://arxiv.org/abs/2604.02268 | skill 来源 = 外部给定;课程退火撤 skill 内化 | [调研] |
| **Skill0.5** | Skill0.5: Joint Skill Internalization and Utilization for Out-of-Distribution Generalization in Agentic Reinforcement Learning | https://arxiv.org/abs/2605.28424 | Skill0 后续:内化 + 利用 + OOD 泛化 | [调研] |
| **SIRI** | SIRI: Self-Internalizing Reinforcement Learning with Intrinsic Skills for LLM Agent Training | https://arxiv.org/abs/2606.02355 | skill 来源 = 策略自挖 | [调研] |

### D. 评测环境 & 数据集(—"在哪训 / 在哪测")

| 简称 | 标题 | 链接 | 角色 | 状态 |
|---|---|---|---|---|
| **OSWorld** | OSWorld: Benchmarking Multimodal Agents for Open-Ended Tasks in Real Computer Environments | https://arxiv.org/abs/2404.07972 | 端到端真环境评测 | [调研] |
| **Video2GUI** | Video2GUI: Synthesizing Large-Scale Interaction Trajectories for Generalized GUI Agent Pretraining | https://arxiv.org/abs/2605.14747 | 路径三 video→轨迹 pipeline 基石(借 B 提取 + C grounding) | [精读] |
| **OS-Atlas** | OS-ATLAS: A Foundation Action Model for Generalist GUI Agents | https://arxiv.org/abs/2410.23218 | 训练源候选(跨平台 grounding) | [调研] |
| **OmniAct** | OmniACT: A Dataset and Benchmark for Enabling Multimodal Generalist Autonomous Agents for Desktop and Web | https://arxiv.org/abs/2402.17553 | 训练源候选(桌面小控件) | [调研] |
| **ScreenSpot-Pro** | ScreenSpot-Pro: GUI Grounding for Professional High-Resolution Computer Use | https://arxiv.org/abs/2504.07981 | step-wise grounding 评测 | [调研] |
