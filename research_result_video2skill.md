# Research Result: 训练模型从操作视频自动抽取多模态 agent skill

## 1. 概览
- **主题**: 让 agent 面对操作视频,自动定位、去噪、提取**可复用的多模态 skill**(范式可借 Visual Skills 的 static/dynamic/interleaved 三型);并探明**训练数据从哪来 + 用什么训练方式**。
- **时间范围**: 2026.1–2026.6.15 为主,纳入少量奠基性窗外工作(2023.04–2025.12)。
- **论文数**: 32(全文精读 ~26;⚠️ 摘要级 6:AtlasVA/ToolTok/SkillWeaver/Video2GUI/AgentTrek/StepFormer 部分)。
- **检索方式**: arXiv 关键词 + 三路雪球;全文经远端代理通道抓取(本机直连被墙)。
- **配套**: 逐篇 notes 见 `paper_list_video2skill.md`。

## 2. 论文清单(按时间升序)
- [2023.04] StepFormer — 字幕自监督发现+定位教学视频步骤。 (2304.13265)
- [2024.06] VideoGUI — 教学视频派生的视觉中心 GUI 分层评测。 (2406.10227)
- [2024.09] Agent Workflow Memory — 从轨迹归纳可复用工作流注入记忆。 (2409.07429)
- [2024.12] AgentTrek — 网页教程引导回放合成 GUI 轨迹(含视频)。 (2412.09605)
- [2024.12] OS-Genesis — 逆向任务合成+TRM 自动造 GUI 轨迹。 (2412.19723)
- [2025.03] SBD/Open-World Skill Discovery — 预测误差自监督切分未分段视频技能边界。 (2503.10684)
- [2025.04] SkillWeaver — web agent 自主发现+打磨 API 技能。 (2504.07079)
- [2025.04] TongUI — 多模态教程→百万 GUI 轨迹(GUI-Net-1M)+SFT。 (2504.12679)
- [2025.08] NoteIt — 教学视频→可交互层级笔记。 (2508.14395)
- [2025.09] EgoInstruct — 面对面教学第一人称视频数据集(步骤分割)。 (2509.22019)
- [2025.12] SAGE — SFT 冷启动+Skill-Augmented GRPO,技能库融入 RL。 (2512.17102)
- [2026.02] SkillRL — 经验蒸馏+技能库与 RL 策略递归协同进化。 (2602.08234)
- [2026.02] ToolTok — GUI 操作 token 化+课程训练,4B 竞争 235B。 (2602.02548)
- [2026.02] Anchor — 分支点+状态锚定变体+验证过滤,桌面轨迹自举。 (2602.07153)
- [2026.03] XSkill — 视觉接地双流(经验+技能)免训练持续学习。 (2603.12056)
- [2026.03] Trace2Skill — 并行归纳整合轨迹→可迁移 SoP(免训免检索)。 (2603.25158)
- [2026.03] KARL — agentic 合成数据+迭代大批量 off-policy RL。 (2603.05218)
- [2026.03] Automating Skill Acquisition — 挖掘开源仓库→SKILL.md(免训)。 (2603.11808)
- [2026.03] CUA-Suite — ~55h/600 万帧连续视频+稠密标注 CUA 数据生态。 (2603.24440)
- [2026.04] Skill-SD — 技能作动态特权信息条件化 teacher,reverse-KL 自蒸馏。 (2604.10674)
- [2026.04] SKILL0 — in-context RL+渐撤课程把技能内化进参数。 (2604.02268)
- [2026.05] MMSkills — 轨迹→状态条件化多模态技能包(文本+状态卡+关键帧)。 (2605.13527)
- [2026.05] AtlasVA — teacher-free 三层视觉技能记忆+记忆增强 RL。 (2605.17933)
- [2026.05] SE-GA — 测试时记忆扩展+记忆数据回灌两阶段训练。 (2605.16883)
- [2026.05] MIND-Skill — 归纳-演绎双 agent+三文本损失(TextGrad)质量保证。 (2605.08670)
- [2026.05] CODESKILL — 技能抽取+维护建模为可学习 RL 管理策略(混合奖励)。 (2605.25430)
- [2026.05] Video2GUI — 视频→大规模 GUI 交互轨迹做预训练。 (2605.14747)
- [2026.05] OmniGUI — 全模态(图+音+视频)手机 GUI 步级 benchmark。 (2605.18758)
- [2026.06] Visual Skills/AutoVisualSkill — 技能超越文本:三型视觉技能+自动构造。 (2606.01414)
- [2026.06] Workflow-to-Skill — Skill-IR/WSA 三元分解把轨迹转可执行 Skill。 (2606.06893)
- [2026.06] MMG2Skill — 现实图文导引→固定VLM条件化+轨迹根因反馈自进化。 (2606.01993)
- [2026.06] VisualClaw — 混合编码+失败驱动离线进化文本技能库。 (2606.16295)

## 3. 分类体系(MECE)

### 类别一:技能的"表示形态"(skill 长什么样)
- **问题**: 可复用知识用什么承载。
- **谱系**: 纯文本 SoP(Trace2Skill/W2S/SkillRL)→ 文本+轻视觉引用(MMSkills 状态卡+关键帧)→ 三型视觉技能(Visual Skills:static 参考图 / dynamic 运行时渲染协议 / interleaved 步骤绑证据)→ 多层视觉记忆(AtlasVA 热图/范例/文本)。
- **共性**: 都在"文本逻辑 + 视觉支撑"之间取舍;越视觉中心的任务越需要显式视觉先验(Visual Skills 实证:计数/grounding 上视觉技能显著优于纯文本)。

### 类别二:技能的"获取方式"(怎么从经验里造出来)
- **轨迹归纳/蒸馏(免训练)**: MMSkills、XSkill、Trace2Skill、W2S、MIND-Skill、Automating Skill Acquisition、AWM、AutoVisualSkill —— 用 LLM/VLM 把轨迹总结/归纳/合并成技能,不更新权重。
- **自监督从视频切分(无标注)**: **SBD(预测误差检测技能边界)**、**StepFormer(字幕 order-aware loss 发现步骤)** —— 直接从海量未标注视频里"去噪+切关键步",最贴你的 idea。
- **数据合成→再训练**: TongUI/AgentTrek/OS-Genesis/Anchor/Video2GUI —— 把教程/视频/探索变成轨迹数据,再 SFT。

### 类别三:技能与策略的"训练耦合"(怎么把技能训进/用好)
- **技能当上下文(in-context/记忆)**: AWM、XSkill、MMSkills、MMG2Skill、VisualClaw —— 注入不更新权重。
- **技能进 RL**: SkillRL(递归协同进化)、SAGE(Skill-Augmented GRPO+Sequential Rollout)、CODESKILL(可学习 RL 管理策略+混合奖励)、KARL(off-policy RL)、SKILL0(in-context RL 内化)。
- **技能进蒸馏**: Skill-SD(技能条件化 teacher 的 reverse-KL 自蒸馏)、MIND-Skill(TextGrad 三损失)。

### 类别四:数据/评测基建
- **数据来源**: 网页教程(TongUI/AgentTrek)、连续操作视频(CUA-Suite/Video2GUI)、第一人称 how-to(Ego4D/EgoInstruct)、游戏视频(SBD)、合成探索(OS-Genesis/Anchor)。
- **benchmark**: GUI(ScreenSpot/-v2、GroundUI-18K、OSWorld、AndroidWorld、VideoGUI、OmniGUI)、agentic 工具(AppWorld、BFCL-v3、VisualToolBench)、计数/视觉(CountBenchQA)、video-QA(Video-MME/EgoSchema)。

## 4. 数据来源盘点(你的"数据从哪来")
| 来源类型 | 代表 | 形态 | 适配你的点 |
|---|---|---|---|
| 网页教程(图文+视频) | TongUI(GUI-Net-1M 100万)、AgentTrek | 教程→任务+分步+截图/视频 | 现成"操作流程"语料,自带弱标注(ASR/步骤) |
| 连续操作视频(桌面) | **CUA-Suite/VideoCUA(55h/600万帧/30fps+光标轨迹+每步推理标注)** | 连续录屏+稠密标注 | **最接近"操作视频→skill"的高质量监督**;含因果监督 |
| 视频→轨迹合成 | **Video2GUI**、OS-Genesis、Anchor | 视频/探索→交互轨迹 | 把视频变成可训练动作序列的现成管线 |
| 第一人称 how-to | Ego4D/EgoExo4D、EgoInstruct | egocentric 视频+keystep | 物理世界操作技能;Goal-Step 定位标注 |
| 游戏/开放世界视频 | SBD(Minecraft YouTube) | 未分段长视频 | 验证"自监督切技能边界"的成熟范式 |
| 评测视频 | VideoGUI、OmniGUI | 专业软件/全模态手机 | 直接当下游 skill 有效性评测 |

**结论**:你不缺数据——**桌面**走 CUA-Suite/Video2GUI/TongUI;**物理操作**走 Ego4D/EgoExo4D;**冷启动监督**可借教程自带的 ASR/步骤弱标注。

## 5. 训练方式盘点(你的"用什么训练")
- **自监督切分(最对口、无需人工标注)**: SBD 用"预训练动作预测模型的预测误差"找技能边界;StepFormer 用"字幕 order-aware loss"发现步骤并过滤无关。→ 直接给你"从视频去噪提关键步"的可训练信号。
- **冷启动 SFT + RL(主流强化路线)**: SAGE/SkillRL/CODESKILL = 先用(合成/专家)轨迹 SFT,再 RL(GRPO 系)让技能与策略协同进化;奖励常用"结果奖励 + 技能整合/质量奖励(rubric)+ 可验证执行反馈"。
- **质量保证的技能生成**: MIND-Skill 的三文本损失(reconstruction/outcome/rubric)+ TextGrad,可直接用来给"提取出的 skill"打质量分(去噪正则)。
- **蒸馏内化**: Skill-SD(技能只条件化 teacher,reverse-KL 蒸给 student)、SKILL0(渐撤技能上下文的课程把技能内化进参数)→ 让模型最终不依赖运行时检索。
- **免训练基线**: MMSkills/XSkill/W2S/Trace2Skill —— 起步可先免训练跑通"视频→skill→用",再上训练。

## 6. 未解决问题 / 值得探索的方向(Gaps)
- **Gap 1 · "视频→多模态skill"几乎空白**: 现有要么"视频→轨迹"(Video2GUI/TongUI,产物是动作序列不是 skill),要么"轨迹→skill"(MMSkills/XSkill,输入是已结构化轨迹)。**没人端到端"从原始操作视频直接提取含视觉先验的可复用 skill"**。为什么是 gap:两段被分别解决,但"视频里哪几帧/哪段是可复用 skill、且该配哪种视觉先验"没人联合学。
- **Gap 2 · 去噪/关键性没有显式监督**: SBD/StepFormer 能切"步骤边界",但"哪一步值得固化成**跨任务可复用 skill**(而非一次性动作)"缺判据。为什么是 gap:可复用性 ≠ 步骤边界,需要跨视频的复现频率/迁移收益信号。
- **Gap 3 · dynamic prior 几乎没人能真生成**: Visual Skills 提出 dynamic prior(运行时渲染),但其代码是协议、靠模型吐合法坐标;你已实测强模型(235B)逐轮自标注命中仅 2/24、grounding 偏移大。为什么是 gap:dynamic skill 的"自标注"质量是真瓶颈,无人训练专门的标注器。
- **Gap 4 · skill 质量缺"可验证"奖励**: Trace2Skill 指出"自生成技能少有用";CODESKILL/MIND-Skill 用 rubric/执行反馈,但**视觉 skill 的质量验证**(看图对不对、复用是否真省步)还没标准。
- **Gap 5 · 评测错位**: 现有 benchmark 评"任务成功率",不直接评"提取出的 skill 好不好、可复用度多高"。

## 7. Research Ideas

### Idea 1 — Video2MMSkill:从操作视频端到端提取多模态 skill(主线)
- **动机**: 对应 Gap 1+2。
- **思路**:
  1. **切分**:借 SBD 的"预测误差/事件分段"把操作视频切成候选 skill 片段(无监督去噪,排除无关帧)。
  2. **可复用性打分**:跨视频统计片段的"复现频率 + 迁移收益"作弱标签,训一个 reusability scorer 选出真正可复用片段(解决 Gap 2)。
  3. **多模态封装**:对选中片段用 MMSkills/Visual Skills 范式生成技能卡(文本流程 + 状态卡 + 关键帧=static prior;需追踪的步骤配 dynamic prior 协议)。
  4. **训练**:冷启动用教程自带 ASR/步骤弱标注做 SFT(StepFormer 式 order-aware loss);再用"下游任务用了该 skill 后的成功率/省步"作 RL 奖励(SkillRL/SAGE 式)。
- **可行性**: 数据=CUA-Suite(连续视频+标注)+TongUI(教程)+Ego4D;切分/打分可先在 OSWorld/AndroidWorld 子集验证;算力中等(scorer 小模型 + VLM SFT/RL)。难点=可复用性弱标签的构造。

### Idea 2 — 训练一个"dynamic-prior 自标注器"(攻 Gap 3,直接接你刚做的实验)
- **动机**: 你已证明强 VLM 直接逐轮自标注(计数)命中很低;Visual Skills 的 dynamic prior 卡在"模型吐不准坐标"。
- **思路**: 把"在图上画锚点/轨迹"做成专门技能:用 CUA-Suite 的**运动学光标轨迹 + 每步标注**作监督,SFT 一个轻量标注器(或给 235B 做坐标 grounding 的 RL,奖励=锚点落在真目标 22px 内);再把它当 dynamic-prior renderer 插回 agent。
- **可行性**: 监督信号现成(光标轨迹=真锚点);可直接用你远端 235B/8B + OSWorld 评测;难点=grounding 精度(与你 MMSkills 复现的坐标问题同源,relative 坐标+补丁可复用)。

### Idea 3 — Skill 质量的可验证奖励 + 去噪(攻 Gap 4/5)
- **动机**: "提取的 skill 是否真可复用"无标准。
- **思路**: 组合 MIND-Skill 的三文本损失(reconstruction/outcome/rubric)+ CODESKILL 的"冻结下游 agent 可验证执行反馈":提取一个 skill 后,让固定 VLM agent 在 held-out 同类任务上**带/不带该 skill** 跑,用 Δ成功率 作 reward 反向优化提取器(类似 MMG2Skill 的根因反馈但带量化奖励)。顺带产出"skill 可复用度"评测指标,补 Gap 5。
- **可行性**: 全程可在固定 VLM 上做(不必训大模型);评测可复用 AppWorld/OSWorld;难点=reward 噪声(需多任务平均)。

### Idea 4 — 弱监督冷启动:用教程的"图文步骤"对齐视频(降数据门槛)
- **动机**: 端到端从零训难;教程(TongUI/AgentTrek)自带"分步指令+截图"。
- **思路**: 把网页教程的步骤文本/截图 当作视频片段的弱标签(对齐 ASR 时间戳),做 StepFormer 式弱监督预训练,再迁移到无教程的纯操作视频。
- **可行性**: TongUI/AgentTrek 开源、规模大;对齐用现成 ASR;难点=教程与视频的时间对齐噪声。

## 附:引用映射(arXiv id · 标题见 paper_list_video2skill.md)
2304.13265 StepFormer · 2406.10227 VideoGUI · 2409.07429 AWM · 2412.09605 AgentTrek · 2412.19723 OS-Genesis · 2503.10684 SBD · 2504.07079 SkillWeaver · 2504.12679 TongUI · 2508.14395 NoteIt · 2509.22019 EgoInstruct · 2512.17102 SAGE · 2602.02548 ToolTok · 2602.07153 Anchor · 2602.08234 SkillRL · 2603.05218 KARL · 2603.11808 AutomatingSkillAcq · 2603.12056 XSkill · 2603.24440 CUA-Suite · 2603.25158 Trace2Skill · 2604.02268 SKILL0 · 2604.10674 Skill-SD · 2605.08670 MIND-Skill · 2605.13527 MMSkills · 2605.14747 Video2GUI · 2605.16883 SE-GA · 2605.17933 AtlasVA · 2605.18758 OmniGUI · 2605.25430 CODESKILL · 2606.01414 VisualSkills/AutoVisualSkill · 2606.01993 MMG2Skill · 2606.06893 Workflow-to-Skill · 2606.16295 VisualClaw
