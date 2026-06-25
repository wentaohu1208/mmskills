# Paper List · Multimodal Agent Skill (2025.10–2026.6.10)

> 18 篇核心论文全文精读 notes（每篇含 skill_representation 重点）。生成日期 2026-06-15。
> 抓取方式：arxiv.org/html/<id> 全文，全部成功，无降级。

---

## 类别一：视觉/Web 多模态技能表示

### MMSkills (2605.13527)
- **title/year/venue**: MMSkills: Towards Multimodal Skills for General Visual Agents / 2026 / arXiv（上交、小红书、东南）
- **problem**: 文本/代码 skill 对视觉 agent 不够用——复用还取决于识别状态、解读进度/失败的视觉证据。
- **method**: (1) skill 包=文本流程+运行时 state card+诊断关键帧；(2) Trajectory-to-Skill 5 阶段生成器；(3) Branch-Loaded Agent 两阶段推理，主 agent 只收压缩结构化引导。
- **skill_representation**: `M=(D,P,S,K)`。D=描述符；P=纯文本流程；S=state card 字段 `(when_to_use, when_not_to_use, visible_cues, verification_cue, available_views)`；K=四视图关键帧 `{full_frame, focus_crop, before, after}`。明确"图是证据，不是坐标"。调用时只给 branch 蒸馏的 `G_t=(applicable, subgoal, plan, do_not_do, verify)`。
- **skill_modalities**: 文本流程 + 结构化 state card + 多视图截图。含图像，无 bbox/坐标。
- **key_results**: OSWorld：Qwen3-VL-8B 10.78%→25.40%，Qwen3-VL-235B 21.34%→39.17%，Gemini3.1Pro 44.08%→50.11%。macOSWorld 55.94%→65.73%，VAB-Minecraft 67.24%→73.28%。
- **data_exp**: OSWorld/macOSWorld/VAB-Minecraft/Super Mario；skill 取自 OpenCUA 公开轨迹。
- **one_line**: 把视觉 agent skill 表示成"文本流程+state card+多视图关键帧证据"，用 branch 加载按需消费。

### Visual Skills / Beyond Text (2606.01414)
- **title/year/venue**: Agent Skills Should Go Beyond Text: The Case for Visual Skills / 2026 / arXiv（北大、UW、MIT-IBM）
- **problem**: 把细粒度视觉线索（边界/命中区/比例）压成文本欠定义；文本无法维护密集感知任务的空间记账。
- **method**: AutoVisualSkill：输入归一化 → visual-bottleneck gate（判定要不要视觉）→ dual-track（语言轨写逻辑/视觉轨抽视觉组件）→ 带 binding rules 的 artifact。
- **skill_representation**: `Sv=(L, Pv, B)`。L=声明式文本逻辑；Pv=视觉支持（static priors 线框/模板、dynamic priors in-situ traces、interleaved references step↔证据绑定）；B=binding protocol。落盘为目录：`skill.md` + `manifest.json` + 视觉资产。prompt 内插 `<visual_prior>[图]</visual_prior>`，**要求返回 JSON `{"point_2d":[x,y],"bbox_2d":[...]}`**。
- **skill_modalities**: 文本逻辑 + 视觉 prior（线框/overlay/带编号锚点/坐标模板）+ 截图。**显式含 bbox/坐标**——视觉成分最重。
- **key_results**: 提出 TDR（文本退化率）。GUI Grounding：Point-in-Box +2.8%，Mean IoU +5.4%。Dense Counting：Exact Acc +4.12 点（93%→97.12%），TDR 高达 58.9%–72.2%。
- **data_exp**: ScreenSpot/GroundUI-18K；CountBenchQA。Qwen3-VL-32B-Thinking、Gemini-2.5-Pro。
- **one_line**: 主张 skill 超越纯文本，用 binding protocol 绑定视觉 prior 与文本逻辑，TDR 量化文本化损失。

### Skill-CMIB (2605.08526)
- **title/year/venue**: Skill-CMIB: Multimodal Agent Skill for Consistent Action via Conditional Multimodal Information Bottleneck / 2026 / arXiv（UCSD、Adobe、UCSB、UNSW）
- **problem**: 多模态 agent 跨试动作不一致；现有方法要么贵（self-consistency 多采样）要么丢视觉（纯文本 card）。
- **method**: CMIB 两阶段——文本阶段瓶颈蒸馏可解释 card；条件多模态瓶颈在 card 条件下压缩残余视觉、降跨模态冗余。
- **skill_representation**: `S=(c,z)`。c=文本 skill card（可检索符号接口）；z=多模态 latent 稠密向量（不可读残余感知）。部署时 z→soft tokens 与 card 一起前置喂冻结模型。⚠️ 论文未给真实 card 模板。
- **skill_modalities**: 文本 card + 不可读视觉 latent（soft token）。无显式图像/bbox。
- **key_results**: Multimodal-Mind2Web Step SR 38.91%（vs SC k=5 35.98%），StepCons 41.44%（vs 17.89%）；延迟 3510ms/step（SC k=5 需 17680ms）。ScreenSpot SR 57.9%。
- **data_exp**: Multimodal-Mind2Web、ScreenSpot；Qwen2.5-VL-7B。
- **one_line**: 用条件信息瓶颈把 skill 拆成"文本 card+残余视觉 latent"，不做多采样即提升动作一致性。

### MMG2Skill (2606.01993)
- **title/year/venue**: MMG2Skill: Can Agents Distill In-the-Wild Guides into Self-Evolving Skills? / 2026 / arXiv（南大、快手）
- **problem**: VLM agent 能否把野生多模态指南转成可执行、可自改进的 skill，且不靠 benchmark 分数修订。
- **method**: 闭环 ConstructSkills→Execute→Analyze（根因诊断，不看分数）→Refine（只重写 skill，VLM 冻结）。
- **skill_representation**: 结构化 Markdown `SKILL.md`，四元组 `z=(u 流程, c 适用条件, v 状态线索, q 恢复知识)`，"通过 procedural text、state descriptions 和 referenced guide images 表达"。文本 + 引用指南图，无 bbox。执行期静态。
- **skill_modalities**: 文本 Markdown SOP + 引用指南图像。
- **key_results**: 6 个 VLM 宏平均 +12.8~+25.3 点（130 任务/3 域）；原始指南直接注入反而降性能；早停省 25–53% 尝试。
- **data_exp**: 自建 MMG2Skill-Bench（GUI 40/OSWorld、Game 30/Minecraft、Strategy 60/RLCard）。
- **one_line**: 野生多模态指南→可编辑 `SKILL.md`，执行-诊断-重写闭环自演化。

### ContractSkill (2603.20340)
- **title/year/venue**: ContractSkill: Repairable Contract-Based Skills for Multimodal Web Agents / 2026 / arXiv（有代码）
- **problem**: 自生成 web skill 平均无收益，因 skill 隐式、不可检查、不可局部修复。
- **method**: 转成显式可执行"契约"：确定性验证 + 故障定位 `(step_index,error_code,trace)` + 5 种最小补丁算子 + execute-diagnose-patch-validate 循环。
- **skill_representation**: `s=(g goal, P 前置, U 步骤, Q 后置, R 恢复, T 终止)`；步骤 `u=(sel DOM选择器, act 动作, arg 参数, Π 断言)`。视觉走 DOM 快照/可访问性摘要，**skill 本体无图像/bbox**。
- **skill_modalities**: DOM selector+动作+断言的可执行文本契约。最"代码化"。
- **key_results**: VisualWebArena 28.1%/37.5%（vs 自生成 9.4%/10.9%）；跨模型迁移 VWA 80.4%（+47.8 点）。
- **data_exp**: VisualWebArena、MiniWoB；GLM-4.6V、Qwen3.5-Plus。
- **one_line**: web skill 做成带 selector/断言/恢复的可执行契约，支持步骤级验证与最小补丁、可跨模型迁移。

---

## 类别二：计算机使用 / 持续学习 / 多智能体多模态技能 + 综述

### CUA-Skill (2601.21123)
- **problem**: CUA 把桌面建模为扁平低层动作，缺可复用结构化技能抽象。
- **method**: 参数化技能 + 执行图 + 组合图；检索增强 skill planner 动态检索/实例化，GUI grounding 或脚本执行。
- **skill_representation**: `S={τ 应用, I 意图, A 参数池(带 type slot), Ge 参数化执行图}`；执行图节点=控制状态、边=GUI 原语(click/type/hotkey)/脚本，受 UI 谓词守卫；组合图节点=技能、边=合法组合。**坐标不存技能**，由运行时 GUI grounding model 预测。例：`FileExplorerCreateNewFolder`=HotKey(Ctrl+L)→Type("Downloads")→Enter→Ctrl+Shift+N→Type("Logs")。
- **skill_modalities**: 文本+图结构(DAG)+过程性代码+参数+UI 谓词逻辑。视觉不嵌入技能。
- **key_results**: 库 452 原子技能/17 应用；WindowsAgentArena best-of-3 57.5%（SOTA）。
- **one_line**: 参数化执行图+组合图把桌面交互编码为可复用技能库，WAA 达 SOTA。

### XSkill (2603.12056, ICML 2026)
- **problem**: 多模态 agent 工具使用低效；缺不更新参数从轨迹持续改进的机制；纯文本抽取丢视觉决策信号。
- **method**: 双流——task-level 技能 + action-level 经验。视觉锚定摘要+跨 rollout 批判蒸馏；推理时按视觉上下文检索注入 system prompt。训练-free。
- **skill_representation**: 技能 `k=(M metadata, W workflow, P tool templates)`，存为 Markdown（YAML frontmatter name/description/version + Strategy Overview + Workflow + Tool Templates(Python 占位符[TARGET]) + Watch Out For）。经验 `e=(c 上下文, a 响应, v 向量)`，≤64 词。**技能本体不含图像/bbox**，视觉只在抽取时 grounding。
- **skill_modalities**: 文本+Python 代码模板+查询模板。不含视觉。
- **key_results**: Average@4 多 backbone +2.58~+6.71；对 Agent-KB 在 TIR-Bench +11.13。
- **one_line**: 视觉锚定抽出"Markdown 技能+文本经验"双流，训练-free 持续改进。

### SkillGraph (2604.17503)
- **problem**: 视觉多智能体系统通信拓扑静态且纯文本（忽略视觉），推理能力部署期冻结。
- **method**: Multimodal Graph Transformer 联合编码图像 patch+指令，动态预测查询条件化通信拓扑；Skill Designer 从失败精炼启发式，技能 embedding 反馈拓扑形成协同进化。
- **skill_representation**: 技能 `s=(c_trig 触发条件, d_strat 策略描述, π 准确率估计, F failure buffer, ν 版本)`，**纯文本**。"多模态"在拓扑层(MMGT 融图像 patch)，技能本身仍是自然语言启发式。
- **skill_modalities**: 技能单模态(纯文本)；系统输入多模态。
- **key_results**: MMBench/MathVista/RealWorldQA/InfoVQA 平均 +1.4–2.0%；约 15–20 轮收敛。
- **one_line**: 技能 embedding 重塑拓扑、拓扑路由塑造技能进化的闭环 VMAS。

### Survey: Agentic Multimodal LLMs (2510.10991)
- **method**: 三维度——internal intelligence / external tool invocation / environment interaction。
- **skill_representation**: ⚠️ 不按 skill 表示形式分类。最接近的是 Action Space 的 token 格式（Specific Tokens `<action_1>` vs Unified Tokens `<action>`+JSON）与 Memory 分类。明确未对技能模态做分类学。
- **one_line**: agentic MLLM 三维综述，但无技能表示形式分类。

### Survey: Agent Skills Taxonomy (2605.07358)
- **method**: 生命周期 representation→acquisition→retrieval→evolution。
- **skill_representation**: 技能 `S=(M 根指令文档, R 辅助资源, C 适用条件)`。表示分类只按资源配置三类：**Text-backed / Code-backed / Hybrid-resource**。⚠️ 明确承认"多模态/视觉技能的表示分类 underdeveloped"，视觉技能仅零星提及（DAMCS/JARVIS-1/XSkill）。
- **one_line**: agent skills 生命周期综述，但表示分类仅 text/code/hybrid，未覆盖视觉模态。

---

## 类别三：机器人 / VLA 技能库（skill=语义标签+神经策略/轨迹/路由）

### AtomicVLA (2603.07648)
- **method**: 单 VLM 自适应 think/act；Skill-Guided MoE（共享专家+技能专用专家）；每技能映射固定 embedding 做路由；学新技能只加专家不重训。
- **skill_representation**: skill=语义标签（如 Pick/Place/Open/Close/Turn）+ 路由 embedding `Z_σ=E(norm(log σ))` + 专用 SwiGLU 神经专家。技能不是完整策略也不是长描述。
- **skill_modalities**: 多相机视觉+语言指令+本体状态→低层动作块。
- **key_results**: LIBERO 96.6%，LIBERO-LONG 95.2%（+10%）；持续学习 +21%、退化仅 -1.3%。
- **one_line**: 长程任务拆原子技能抽象路由到 MoE 专家，高效长程+无遗忘终身学习。

### Uni-Skill (2603.02623)
- **method**: Skill-Aware Planning 检测技能缺口并合成新技能描述；Automatic Skill Evolution 从分层视频库 SkillFolder 检索示范 grounding 成动作。
- **skill_representation**: skill=自然语言描述（语义标签）+ 可带参调用的 code API + 执行四件套（接触点/6-DoF 路点/语义约束/轨迹参考）。VerbNet 式 4 层 SkillFolder（106 类→1659 描述→~1 万视觉实例）。
- **skill_modalities**: 视觉(RGB/深度)+语言+动作(SE(3) 轨迹)。
- **key_results**: RLBench OOD 0.41（vs MOKA 0.10）；真机 0.73（vs 0.39）；库由 350h DROID 视频构建。
- **one_line**: 检测技能缺口、合成新描述、从分层自动标注视频库检索 grounding，超越固定技能集泛化。

### Atomic Action Slicing (2512.11584, SAC 2026)
- **method**: 三阶段把长程视频切成带类型原子动作：planner 生成动作序列→schema 约束 LLM 提议时间边界→count/order/duration 验证。
- **skill_representation**: 符号五元组 option：`Name(place_bowl_in_drawer) + Preconditions(类PDDL谓词) + Termination + Postconditions + Temporal Span(帧+置信度)`。STRIPS/HTN 兼容，**无神经策略也无 API**。
- **skill_modalities**: 视觉(窗口视频帧)+符号(任务描述+BDDL 场景)+动作日志。
- **key_results**: 切分 93/100；LIBERO-Long 83.8%→88.8%（+5.0pp）；产 2124 原子段（公开 GATE-VLAP）。
- **one_line**: 符号引导切分长程示范为 planner 兼容原子动作，改善 VLA 微调与组合规划。

### LiLo-VLA (2602.21531)
- **method**: 解耦运送(经典运动规划 MPLib)与交互(物体中心 VLA)；闭环失败恢复回溯到上次 Pick。
- **skill_representation**: skill=参数化谓词 `α_i(o_i, ρ_i)`（原语类别+参考物体+约束）+ 物体中心神经策略（OpenVLA-OFT/Pi0.5；腕载视角+黑遮挡干扰物+相对物体坐标系）。
- **skill_modalities**: 视觉(腕部 RGB)+语言+动作+本体相对位姿。
- **key_results**: 仿真 21 任务 69%（vs Pi0.5 28%）；真机 8 任务标准 100%。
- **one_line**: 运动规划+物体中心 VLA 解耦，零样本组合泛化+稳健恢复。

---

## 类别四：具身反思 / 技能更新治理 / 多模态游戏

### EmbodiSkill (2605.10332)
- **method**: Skill-Aware Reflection 产 4 类信号（DISCOVERY/OPTIMIZATION/SKILL DEFECT/EXECUTION LAPSE）；Skill Revision 整合，training-free 进化螺旋。
- **skill_representation**: skill=自然语言"持久可修订程序性规范"（前置/子目标排序/物体可供性/视觉搜索策略/动作前置/恢复）。双组件 `S=(S_body, S_app)`：body 处方式内容，appendix 强调要遵守的内容。文本经 prompt 给冻结执行器。⚠️ 无 JSON/字段样例。
- **skill_modalities**: 技能纯文本；输入含语言+RGB 视觉。
- **key_results**: ALFWorld 93.28%（+31.58pp vs GPT-5.2）；vs skill-unaware +19.04% 相对。
- **one_line**: training-free 具身技能自进化，区分技能缺陷 vs 执行失误做选择性修订。

### Atomic-Probe Governance (2604.26689)
- **method**: Atomic-Quality Probe `q(c)=P(success|c alone)`；Hybrid Selector 按原子质量差决定信任原子信号还是组合重验证。
- **skill_representation**: skill=神经策略控制器（Embodied Capability Module，时序抽象 option）。策略分 reach/grasp/lift/place 四阶段，每阶段一个 SAC 控制器。组合 `C=(c1,c2,c3,c4)`。**纯神经，无符号/语言**。
- **skill_modalities**: 纯状态(state-based)，无视觉无语言。
- **key_results**: 主导技能效应 86.7% vs 26.7%；swap 偏移 ±50pp；Hybrid(m=10) 75.0%@45.8% 成本。
- **one_line**: 用单技能独立成功率原子探针+选择性重验证治理技能替换。

### CLASP (2606.08169)
- **method**: 学习阶段动觉示教训 TP-KMP + VLM 自动生成 JSON schema；执行阶段语言指令→VLM tool-calling 匹配/参数化→TP-KMP 生成轨迹；product-of-Gaussians 组合；主动学习补缺口。
- **skill_representation**: skill=`(Θ, ϕ)` 二元组。Θ=TP-KMP 轨迹模型（local KMP 均值+协方差，frame-relative）；ϕ=VLM 生成的 **JSON tool-definition schema**（物体数量/类型、语义标签 grasp/pour/insert、交互顺序、前置条件）。
- **skill_modalities**: 轨迹分布+物体 6D 位姿参数化+VLM 视觉-语言 schema。
- **key_results**: 物体泛化 90.9%（4 示教，vs π0.5 0%）；组合 100%；缺口检测 95%。
- **one_line**: TP-KMP+VLM 结合，语言驱动技能选择/组合/主动获取，无需微调。

### Learning to Play (2510.16774)
- **method**: 单一整体式文本条件 model-free 策略 Pixels2Play（~400M decoder-only transformer），画面→键鼠动作。
- **skill_representation**: **无正式 skill 抽象**（无技能库/分解/原语）。替代物是运行时文本条件指令（如 "pick up the shotgun"）。轨迹标注 JSON `{narrative, instructions:[{start,end,instruction}]}`。⚠️ 实质是"无技能"对照点。
- **skill_modalities**: 视觉游戏画面+文本指令→键鼠动作。
- **key_results**: 简单游戏达新手人类水平；长程差。无 per-skill 指标。
- **one_line**: 7000h 标注+16000h IDM 补全训练实时多 3D 游戏策略，但无技能抽象。

---

## 横向小结：skill 表示形式光谱

| 形式 | 论文 | skill 本体长什么样 |
|------|------|-------------------|
| 纯文本/Markdown SOP（视觉只引用/运行时输入） | XSkill, MMG2Skill, EmbodiSkill, SkillGraph | YAML+workflow+代码模板 / SKILL.md 四元组 / body+appendix 规范 / 触发条件+策略文本 |
| 结构化文本+显式视觉证据（图存进 skill） | MMSkills, Visual Skills | state card+四视图关键帧 / skill.md+manifest.json+bbox/坐标/overlay |
| 可执行契约/代码化文本 | ContractSkill, CUA-Skill | (g,P,U,Q,R,T)+DOM selector / 执行图+组合图 DAG+GUI 原语 |
| 文本 card+不可读视觉 latent | Skill-CMIB | 文本 card + soft token 向量 |
| 语义标签+神经策略/路由/轨迹（机器人/VLA） | AtomicVLA, Uni-Skill, LiLo-VLA, Atomic-Probe, CLASP, Atomic Action Slicing | 标签+MoE 专家 / 描述+code API+轨迹库 / 谓词+物体中心策略 / 神经 option / TP-KMP+JSON schema / 符号五元组 option |
| 无 skill 抽象（对照） | Learning to Play | 仅运行时文本指令 |
| 综述（未覆盖视觉技能表示） | Survey 2510.10991, Survey 2605.07358 | text/code/hybrid 三类，自陈视觉表示未成熟 |
