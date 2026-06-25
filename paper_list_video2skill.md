# Paper List — 从操作视频自动抽取多模态 agent skill(2026.1–2026.6.15 为主,含关键窗外)

> 每篇固定 schema。数据来自 arXiv 全文/摘要(走远端代理抓取);标 ⚠️ 者为抓取占位失败、依据本会话 WebSearch 摘要补全,精度待核。字段缺失标"未明(提取未覆盖)"。生成于本轮 survey。

---

## A1 · 多模态技能抽取/生成

### [2603.12056] XSkill: Continual Learning from Experience and Skills in Multimodal Agents
- year/venue: 2026.03 / ICML 2026
- problem: 多模态 agent 工具使用低效、编排死板;如何不更新参数地从过去轨迹持续自改进。
- method: 双流——experiences(动作级)+ skills(任务级),抽取与检索都视觉接地;Phase I 多路径 rollout 经视觉接地总结+跨rollout互批→蒸馏整合;Phase II 检索适配当前视觉上下文,使用历史回流成闭环。
- training: **training-free**(无参数更新)。
- data_exp: 数据=agent 自身多路径 rollout 轨迹;5 benchmark × 4 backbone(VisualToolBench/TIR-Bench/MMSearch-Plus/AgentVista/MMBrowseComp)。
- key_results: 一致大幅超 tool-only 与 learning-based 基线;zero-shot 跨任务迁移更优。
- novelty: 首次"经验+技能"双流且全程视觉接地;积累↔推理持续闭环。
- one_line: 视觉接地的双流(经验+技能)框架,多模态 agent 无需训练持续自改进。

### [2605.13527] MMSkills: Towards Multimodal Skills for General Visual Agents
- year/venue: 2026.05 / arXiv
- problem: 程序性知识本质多模态;技能包该含什么、从哪导出、推理时怎么用而不污染上下文。
- method: 每个 MMSkill=文本流程+状态卡+多视角关键帧;agentic"轨迹→技能 Generator"(workflow grouping/procedure induction/visual grounding/meta-skill audit);分支加载 agent 临时分支检视后蒸馏给主 agent。
- training: **training-free**(Generator 自动构造,非微调)。
- data_exp: 数据=公开非评测交互轨迹;评测 GUI + game-based(含 OSWorld)。
- key_results: 一致提升 frontier 与较小多模态 agent。
- novelty: 技能升级为状态条件化多模态包;分支加载消费视觉证据不过度锚定。
- limitations: 强模型几乎不触发技能机制(你的复现:235B mm≈base,弱 8B 才增益)。
- one_line: 把公开轨迹自动编译为状态条件化多模态技能包,分支加载供视觉 agent 用。

### [2605.17933] AtlasVA: Self-Evolving Visual Skill Memory for Teacher-Free VLM Agents ⚠️(据检索摘要)
- year/venue: 2026.05 / arXiv
- problem: VLM agent 靠记忆增强 RL 复用经验,但多数把记忆存纯文本、依赖专有 teacher 模型总结。
- method: teacher-free 视觉技能记忆,三层:空间热图 / 视觉范例 / 符号文本技能。
- training: 记忆增强 RL,**teacher-free**。
- data_exp: 长程 VLM agent 任务(benchmark 待核全文)。
- novelty: 三层视觉记忆 + 无 teacher 自进化。
- one_line: 无 teacher 的三层(热图/范例/文本)视觉技能记忆,支撑 VLM agent 自进化。

### [2605.16883] SE-GA: Memory-Augmented Self-Evolution for GUI Agents
- year/venue: 2026.05 / arXiv
- problem: GUI agent 受上下文窗口+静态策略限,难适应动态环境。
- method: 分层记忆+迭代自改进。TTME 推理时检索 episodic/semantic/experiential 记忆并实时累积成功轨迹做在线进化;MASE 两阶段训练用 TTME 筛出的高质量数据增强 VLM。
- training: **含训练**(MASE 两阶段;用记忆筛出数据微调 VLM;SFT/RL 未明)。
- data_exp: 数据=TTME 累积的成功轨迹(自生成);评测 ScreenSpot/AndroidControl-High/GUIOdyssey/AndroidWorld。
- key_results: ScreenSpot 89.0%、AndroidControl-High 75.8%;称 SOTA。
- novelty: 测试时记忆扩展(在线)+记忆数据回灌两阶段训练(离线)闭环。
- one_line: 分层记忆测试时扩展并回灌训练,GUI agent 在线自进化刷新 SOTA。

### [2606.01414] Agent Skills Should Go Beyond Text: The Case for Visual Skills (AutoVisualSkill)
- year/venue: 2026.06 / arXiv(立场+系统)
- problem: 现有技能多存纯文本,对视觉任务(空间布局/视觉锚定/细粒度外观/局部状态)是根本瓶颈。
- method: Visual Skill=文本逻辑+视觉支撑;三类:static priors(静态参考图)/dynamic priors(运行时画的视觉工作记忆)/interleaved(文本步骤绑定源截图)。AutoVisualSkill 自动从轨迹保留文本推理+空间引用+视觉边界→多模态技能。
- training: **training-free**(自动构造系统)。
- data_exp: 数据=任务轨迹;评测 GUI(ScreenSpot/-v2/GroundUI-18K,Qwen3-VL-32B-Thinking)+计数(CountBenchQA,Gemini-2.5-Pro)。
- key_results: 视觉技能一致优于纯文本;计数 Visual 97.12% vs 文本 93.00% vs 无 94.24%,MAE 降~60%,+4.12(p=0.003);GUI Mean IoU +0.054。
- novelty: 技能"超越文本成多模态一等资产";三类范式;代码仓库给 dynamic renderer 协议。
- limitations: dynamic 依赖模型吐合法坐标(你实测 235B grounding 偏移大、逐轮自标注命中低 2/24)。
- one_line: 主张技能应多模态,给 static/dynamic/interleaved 三类+AutoVisualSkill 自动构造。

### [2606.01993] MMG2Skill: Can Agents Distill In-the-Wild Guides into Self-Evolving Skills?
- year/venue: 2026.06 / arXiv
- problem: 现实人类导引多模态/异构/含噪/默认人执行,难直接当技能;形式化 guide-to-skill learning。
- method: 闭环——guides 编译成可编辑技能→执行时条件化**固定 VLM**→按轨迹级根因反馈修订(不用 benchmark 分数);建 MMG2Skill-Bench。
- training: **training-free**(VLM 固定;改进来自技能构造+根因反馈)。
- data_exp: 数据=in-the-wild 人类导引语料+执行轨迹反馈;Bench 覆盖 GUI/开放游戏/策略卡牌,6 VLM backbone。
- key_results: 宏平均 +12.8~+25.3pp;消融:原始 guides 直接提示反而降,结构化构造+轨迹修订缺一不可。
- novelty: 形式化 guide-to-skill;首个 benchmark;固定 VLM 上"编译→条件化→根因修订"自进化。
- one_line: 把现实图文导引编译成可编辑技能并用轨迹根因反馈持续修订,固定 VLM 跨域自进化。

### [2606.16295] VisualClaw: A Real-Time, Personalized Agent for the Physical World
- year/venue: 2026.06 / arXiv
- problem: VLM 部署三缺口:密集帧/长 prompt 贵慢;框架部署后静态;标准 video-QA 不测"工作区用视觉证据"。
- method: 自进化多模态 agent:混合编码(级联门过滤帧 + hot/cold top-k 压缩文本技能库)+ 技能进化(失败→离线 evolver→技能库更新);三时间尺度。
- training: **training-free/离线进化**(技能库离线更新,非更新权重)。
- data_exp: 4 video-QA(Video-MME/EgoSchema)×2 VLM;自建 VisualClawArena(200 场景)。
- key_results: 每问 API 成本 -98%(峰 -99.3%);EgoSchema+Gemini 平均 +3.85%/峰 +15.80%;Arena Codex +2.9%/Claude +3.2%。
- novelty: 三粒度混合编码+技能进化;首个"工作区用视觉证据"agentic benchmark;跨 VLM 迁移发现。
- limitations: 技能纯文字(非多模态);格式类技能迁移差。
- one_line: 自进化多模态 agent,混合编码+技能库进化在 video-QA/agentic 大幅降本且提精度。

### [2603.11808] Automating Skill Acquisition through Large-Scale Mining of Open-Source Agentic Repositories
- year/venue: 2026.03 / arXiv(report)
- problem: 通用模型陈述性知识广但缺过程性专长;如何自动可扩展获取技能。
- method: 挖掘 GitHub 仓库→结构分析+稠密检索语义技能识别→翻译成标准 SKILL.md;四阶段安全验证;SkillNet 整合。案例 TheoremExplainAgent/Code2Video(Manim)。
- training: **training-free**(抽取而非微调)。
- data_exp: 数据=开源 agentic 仓库;产出可视化/教育 SKILL.md。
- key_results: 教育内容知识传递效率 +40%。
- one_line: 无需重训,挖掘开源仓库自动抽取可执行 SKILL.md 技能。

### [2606.06893] Workflow-to-Skill (W2S): Skill Creation via Routing-Workflow-Semantics-Attachments Decomposition
- year/venue: 2026.06 / arXiv
- problem: 高质量 Skill 仍靠手写难扩展;轨迹碎片化含冗余、可能漏低频安全操作,非标准摘要问题。
- method: Skill-IR 中间表示,分解为 Workflow结构/执行Semantics/运行时Attachments(WSA);W2S:轨迹切过程单元→单路径归纳草稿→跨场景对齐合并→调和分支→压冗余,保留验证/审批/回滚/状态管理(带证据+置信度);含反馈精炼。
- training: **training-free**(trace-to-skill 结构化生成+反馈精炼)。
- data_exp: 数据=demonstrations/agent轨迹/tool-use traces/execution logs;实验 70 skills。
- key_results: 行为重放一致性 +10.5%(vs 摘要/prompting 基线)。
- novelty: Skill-IR/WSA 三元分解;把轨迹当"可执行运行时规范的证据";保留安全攸关行为。
- one_line: WSA 三元分解把异构轨迹自动转成可执行可验证 Skill,行为重放一致性 +10.5%。

### [2605.08670] MIND-Skill: Quality-Guaranteed Skill Generation via Multi-Agent Induction and Deduction
- year/venue: 2026.05 / arXiv
- problem: 技能策展长期靠人工;如何自动、有质量保证地从成功轨迹归纳可泛化技能。
- method: 双 agent——induction 抽象技能、deduction 按技能重建轨迹;三种文本损失:reconstruction/outcome/rubric loss,用 TextGrad 联合优化;held-out 评测。
- training: **TextGrad 文本梯度优化**(优化技能文本而非权重);显式损失(重建/结果/rubric)。
- data_exp: 数据=成功轨迹;评测 AppWorld、BFCL-v3(held-out)。
- key_results: 一致优于同期(对比 ACE、Trace2Skill);弱模型用之可匹敌前沿模型。
- novelty: 归纳-演绎闭环用"重建验证"归纳;三可解释文本损失+TextGrad 质量保证。
- one_line: 双 agent 归纳-演绎+三文本损失(TextGrad)生成有质量保证的可复用技能。

---

## A2 · 训练方法(RL/SFT/蒸馏/课程)

### [2602.08234] SkillRL: Evolving Agents via Recursive Skill-Augmented Reinforcement Learning
- year/venue: 2026.02 / arXiv(≈用户 skmrl)
- problem: 记忆法多存原始轨迹冗余含噪,难抽高层可复用模式。
- method: 经验蒸馏建层次化 SkillBank→自适应检索(通用 vs 任务特定)→递归进化(技能库与策略在 RL 中协同进化);失败也蒸馏。
- training: **RL(GRPO)**;经验蒸馏+cold-start 轨迹;技能库与策略递归协同进化。
- data_exp: 数据=agent 执行轨迹;ALFWorld/WebShop+7 搜索增强任务。code: aiming-lab/SkillRL。
- key_results: SOTA,超强基线 >15.3%;比 vanilla GRPO/记忆增强 RL 收敛更快。
- novelty: 技能库与 RL 策略递归协同进化;层次化 SkillBank 含失败利用;降 token。
- one_line: 经验蒸馏+技能库与策略递归协同进化,agent 自进化超基线 15.3%。

### [2512.17102] SAGE: Reinforcement Learning for Self-Improving Agent with Skill Library
- year/venue: 2025.12 / arXiv〔窗外·关键〕
- problem: agent 部署新环境难持续改进;技能库多靠 prompting、一致性差。
- method: SAGE=Skill Augmented GRPO;Sequential Rollout(相似任务链内迭代,前序技能累积供后续)+ Skill-integrated Reward 补充结果奖励。
- training: **SFT(专家经验冷启动)+ RL(GRPO)**;奖励=Skill-integrated+outcome。
- data_exp: 数据=专家经验(SFT)+任务链 rollout;评测 AppWorld。code: amazon-science/SAGE。
- key_results: AppWorld 目标完成 +8.9%,步数 -26%,token -59%。
- novelty: Sequential Rollout 让技能在任务链累积复用;技能整合奖励;RL 解决 prompting 一致性差。
- one_line: Sequential Rollout+技能整合奖励把技能库融入 GRPO,AppWorld +8.9% 且更省。

### [2604.10674] Skill-SD: Skill-Conditioned Self-Distillation for Multi-turn LLM Agents
- year/venue: 2026.04 / arXiv
- problem: 多轮 agent RL 受稀疏奖励+长程限;OPSD 固定特权信息覆盖不了多样策略,OPSD+RL 易崩。
- method: 轨迹总结成自然语言"技能"作**动态特权信息只条件化 teacher**(student 始终普通 prompt)蒸馏内化;重要性加权 reverse-KL token 级蒸馏;teacher-student 动态同步。
- training: **RL(GRPO)+自蒸馏**;损失=importance-weighted reverse-KL;λ 平衡。
- data_exp: AppWorld、Sokoban。
- key_results: vs vanilla GRPO +14.0%/+10.9%;vs vanilla OPD +42.1%/+40.6%。
- novelty: "技能指导 teacher 而非 student";重要性加权 reverse-KL 解决 OPSD+RL 崩溃。
- one_line: 轨迹生成技能动态条件化 teacher,reverse-KL 自蒸馏稳定增强多轮 agent RL。

### [2603.25158] Trace2Skill: Distill Trajectory-Local Lessons into Transferable Agent Skills
- year/venue: 2026.03 / arXiv
- problem: 手写技能不可扩展,纯参数知识生成技能常漏操作陷阱。
- method: 对经验归纳推理、并行整合大量轨迹成统一技能目录;三阶段:轨迹生成→并行补丁提案→补丁整合;反复失败+变通压成 SoP。
- training: **training-free**(可移植技能,无需参数更新或测试时检索)。
- data_exp: office/数学/视觉QA(DocVQA);WikiTableQuestions;轨迹用 Qwen3.5-35B。
- key_results: 35B 轨迹技能让 122B 在 WikiTableQuestions 最多 +57.65pp;优于顺序编辑/ReasoningBank。
- novelty: 并行+层次整合;技能跨模型规模/家族/OOD 可迁移。
- one_line: 并行归纳整合轨迹→可跨模型迁移、免训免检索的便携技能(SoP)。

### [2604.02268] SKILL0: In-Context Agentic Reinforcement Learning for Skill Internalization
- year/venue: 2026.04 / arXiv
- problem: 推理时技能增强有根本局限:检索噪声、token 开销、模型从未真正习得。
- method: in-context RL 做"技能内化";训练时课程:先给完整技能上下文再逐步撤除;技能按类分组+与历史渲染成紧凑视觉上下文;动态课程按 on-policy helpfulness 保留有益技能至全 zero-shot。
- training: **RL(in-context RL)+自适应课程**;目标=技能内化进参数,zero-shot 免检索。
- data_exp: ALFWorld/Search-QA/WebShop;技能渲染为视觉上下文。
- key_results: ALFWorld +9.7%/Search-QA +6.6%/WebShop +10.1%;每步上下文 <0.5k tokens。
- novelty: "技能内化"+渐撤课程;on-policy helpfulness 动态课程;紧凑视觉上下文低开销。
- one_line: 渐撤技能上下文的 in-context RL 课程,把技能内化进参数,zero-shot 低 token。

### [2605.25430] CODESKILL: Learning Self-Evolving Skills for Coding Agents
- year/venue: 2026.05 / arXiv
- problem: 编码轨迹可蒸馏成技能,但现有多靠固定 prompt+启发式更新。
- method: 技能抽取+技能库维护表述为**可学习管理策略**;从轨迹抽多粒度技能、用新经验演化、维护紧凑库。
- training: **SFT(监督 warmup)+3 阶段 RL**;混合奖励=密集 rubric 技能质量+稀疏可验证执行反馈(冻结下游 agent)。
- data_exp: 评测 EnvBench/SWE-Bench Verified/Terminal-Bench 2。
- key_results: vs 无技能平均通过率 +9.69;vs 最强 prompt/memory +4.01;技能库稳定。
- novelty: 技能抽取+维护统一为可学习 RL 管理策略;多粒度;混合奖励。
- one_line: 把编码技能抽取+维护建模为可学习 RL 管理策略,混合奖励自演化紧凑库。

### [2603.05218] KARL: Knowledge Agents via Reinforcement Learning
- year/venue: 2026.03 / arXiv
- problem: 训练企业搜索 agent 在多样难验证任务上 SOTA 且泛化、成本可控。
- method: KARLBench(6 范式)+跨异构行为训练+agentic 合成数据(迭代 bootstrapping)+迭代大批量 off-policy RL;测试时 Parallel Thinking+Value-Guided Search。
- training: **RL(迭代大批量 off-policy,多任务)**;数据 agentic 合成;对比 Multi-Expert Distillation vs Multi-Task RL。
- data_exp: 合成训练数据;KARLBench(BrowseComp-Plus/TREC-Biogen);向量搜索为唯一工具。
- key_results: cost/latency–quality Pareto 最优,超 Claude 4.6/GPT 5.2。
- novelty: 迭代大批量 off-policy RL 后训练;agentic 合成数据;RL 泛化超 sharpening。
- one_line: agentic 合成数据+迭代大批量 off-policy 多任务 RL,训出 Pareto 最优企业搜索 agent。

### [2602.02548] ToolTok: Tool Tokenization for Efficient and Generalizable GUI Agents ⚠️(据检索摘要)
- year/venue: 2026.02 / arXiv
- problem: GUI agent 基于坐标的视觉 grounding 数据需求大、泛化差。
- method: GUI 操作建模为渐进工具序列,每工具=可学习 token embedding;语义锚定;易到难课程(token 定义 QA→文本引导工具选择→简化视觉寻路)。
- training: **课程训练+可学习 token embedding**(post-training,<1% 数据)。
- data_exp: GUI 寻路;benchmark 待核全文。
- key_results: 4B 超同级、与 235B 竞争;训练数据 <1%。
- novelty: 工具 tokenization+语义锚定+课程,绕开坐标 grounding。
- one_line: GUI 操作 token 化+课程训练,4B 用 <1% 数据竞争 235B。

### [2504.07079] SkillWeaver: Web Agents can Self-Improve by Discovering and Honing Skills ⚠️(据检索摘要)
- year/venue: 2025.04 / arXiv〔窗外·奠基〕
- problem: web agent 如何自主积累可复用技能。
- method: agent 自主探索发现技能(封装为可复用 API),实践打磨、合成验证,建技能库。
- training: **training-free 探索式自改进**(合成 API 技能)。
- data_exp: web 环境;细节待核全文。
- novelty: 自主发现+打磨技能成 API 库,test-time 自改进。
- one_line: web agent 自主发现并打磨可复用 API 技能,自我改进。

### [2409.07429] Agent Workflow Memory (AWM)
- year/venue: 2024.09 / ICML 2025〔窗外·奠基〕
- problem: LLM agent 长程弱;人类能从经验学可复用流程。
- method: 从轨迹归纳可复用"工作流"(目标+通用例程),选择性注入指导后续;离线+在线(测试时即时归纳,无监督下从 evaluator 判对的历史归纳)。
- training: **in-context/记忆增强**(注入工作流,非参数更新)。
- data_exp: Mind2Web+WebArena(200+ 域、1000+ 任务)。code: zorazrw/agent-workflow-memory。
- key_results: Mind2Web +24.6%、WebArena +51.1% 相对成功率;在线高出基线 8.9~14.0 绝对点。
- novelty: 统一离线/在线+在线无监督地从轨迹归纳工作流注入记忆。
- one_line: 从轨迹归纳可复用工作流注入记忆,大幅提升 web agent 长程成功率。

---

## B · 数据集 / 轨迹数据合成(数据来源)

### [2605.14747] Video2GUI: Synthesizing Large-Scale Interaction Trajectories for Generalized GUI Agent Pretraining ⚠️(据检索标题/主题)
- year/venue: 2026.05 / arXiv
- problem: GUI agent 预训练缺大规模交互轨迹。
- method: 从**视频**合成大规模交互轨迹(把视频里的操作转成可训练动作序列),做通用 GUI agent 预训练。
- training: 预训练(用合成轨迹);范式待核全文。
- data_exp: 数据来源=视频→交互轨迹(大规模);规模/benchmark 待核全文。
- novelty: 直接"视频→GUI 交互轨迹"做预训练数据(与你"操作视频→skill"最对口的数据侧)。
- one_line: 从视频合成大规模 GUI 交互轨迹做通用 agent 预训练。

### [2504.12679] TongUI: Internet-Scale Trajectories from Multimodal Web Tutorials for Generalized GUI Agents
- year/venue: 2025.04 / AAAI 2026〔窗外·关键数据〕
- problem: 通用 GUI agent 缺跨 OS/应用轨迹,人工标注贵。
- method: 海量多模态网页教程(视频+图文)→GUI 轨迹:爬取→ASR/captioning→LLM 产任务+计划→视频抽 salient frame 当每步截图;过滤;GUI-Net-1M;微调 Qwen2.5-VL-3B/7B/32B。
- training: **SFT**(GUI-Net-1M 微调 Qwen2.5-VL)。
- data_exp: GUI-Net-1M=100 万轨迹、5 OS、280+ 应用(最大开源);评测 grounding/navigation。开源。
- key_results: 多 benchmark 较基线约 +10%。
- novelty: "教程(视频+文章)→百万 GUI 轨迹"框架+最大开源集。
- one_line: 把互联网多模态教程转百万 GUI 轨迹并 SFT,低成本训通用 GUI agent。

### [2412.09605] AgentTrek: Agent Trajectory Synthesis via Guiding Replay with Web Tutorials
- year/venue: 2024.12 / ICLR 2025 Spotlight〔窗外·关键数据〕
- problem: GUI agent 缺高质量多步轨迹,人工标注不可持续。
- method: 自动采集教程文本→转任务目标+分步指令→VLM agent 在真实环境模拟执行(含截图+视频录制)→VLM 评估器验证正确性。
- training: 用合成轨迹训练 GUI agent;范式待核。
- data_exp: 数据=网页教程→轨迹(含截图+视频录制+DOM/HTML 日志)。开源 AgentTrek-1.0-32B。
- key_results: 显著提升 grounding/planning,更省成本。
- novelty: "教程引导回放"合成轨迹+VLM 评估器把关。
- one_line: 用网页教程引导 VLM 回放合成高质量 GUI 轨迹(含视频),低成本训 agent。

### [2412.19723] OS-Genesis: Automating GUI Agent Trajectory Construction via Reverse Task Synthesis
- year/venue: 2024.12 / arXiv〔窗外·奠基〕
- problem: GUI 训练轨迹收集瓶颈;预定义任务合成数据质量/多样性差。
- method: 逆转流程——先交互探索再回溯反推任务(Reverse Task Synthesis),轨迹级探索;Trajectory Reward Model(TRM)保质。
- training: 用合成轨迹训练(InternVL2-4B/8B);TRM 把关;SFT/RL 待核。
- data_exp: OS-Genesis 自动合成 GUI 轨迹;高难在线 benchmark。
- key_results: 在线 benchmark 显著提升;数据质量/多样性优于已有合成法。
- novelty: 逆向任务合成+轨迹奖励模型。
- one_line: "先探索后反推任务"逆向合成+TRM,自动造高质量 GUI 训练轨迹。

### [2602.07153] Anchor: Branch-Point Data Generation for GUI Agents
- year/venue: 2026.02 / arXiv
- problem: 桌面 GUI 缺高质量数据;现有合成多样性有限、噪声大、目标漂移。
- method: 少量验证种子演示自举:识别"分支点"(有意义状态变化)→提状态锚定新任务变体→执行 agent 生成新轨迹→verifier 状态感知+轨迹级一致性确认→步级过滤剔无锚定动作+分支后去噪。
- training: **SFT**(扩展语料微调)。
- data_exp: 种子自举的桌面监督语料;评测 OSWorld、WindowsAgentArena。开源 yale-nlp/Anchor。
- key_results: 一致超 zero-shot 与代表性合成基线,跨应用/OS 泛化。
- novelty: 分支点驱动轨迹扩展+状态锚定变体+verifier+步级过滤/去噪(填桌面空白)。
- one_line: "分支点+状态锚定变体+验证过滤"从少量种子自举生成可扩展桌面 GUI 轨迹。

### [2603.24440] CUA-Suite: Massive Human-annotated Video Demonstrations for Computer-Use Agents
- year/venue: 2026.03 / arXiv
- problem: CUA 缺连续高质量人类演示视频(最大开源 ScaleCUA 仅 200 万截图、<20h)。
- method: 大规模专家视频+稠密标注生态。VideoCUA:~10000 任务/87 应用/30fps 连续录屏/运动学光标轨迹/每步~497 词多层推理标注(~55h、600 万帧);配 UI-Vision(评测)+GroundCUA(grounding)。
- training: 数据集/基准(提供训练语料)。
- data_exp: VideoCUA ~55h/600 万帧;GroundCUA 56K 截图、360 万+ UI 元素;评测 UI-Vision。
- novelty: 首个连续 30fps 视频+运动学光标+稠密多层推理标注的大规模 CUA 数据生态;支持视频奖励建模、视觉世界模型。
- one_line: ~55h/600 万帧连续视频+稠密标注的 CUA 数据生态,提供因果监督。

### [2605.18758] OmniGUI: Benchmarking GUI Agents in Omni-Modal Smartphone Environments
- year/venue: 2026.05 / arXiv
- problem: 现有 GUI benchmark 靠静态截图,缺与动作耦合的瞬态音频+时序视频。
- method: 首个全模态手机步级 benchmark,每步给图像+同步音频+视频片段交错输入,按"多模态依赖等级"标注;全模态模型作 proxy 基线。
- training: **training-free**(评测)。
- data_exp: 709 专家演示 episode/2579 步/29 应用,带多模态依赖等级标注。
- key_results: 模型在需同步时序/听觉的环境动作预测显著下降;发现跨模态干扰。
- novelty: 首个图+音+视频交错的全模态手机 GUI 步级 benchmark。
- one_line: 全模态手机 GUI 步级评测,暴露时序/听觉短板与跨模态干扰。

### [2406.10227] VideoGUI: A Benchmark for GUI Automation from Instructional Videos
- year/venue: 2024.06 / NeurIPS 2024 D&B〔窗外·核心〕
- problem: 现有 GUI 任务多为单语言指令简单任务,缺视觉中心复杂软件评测。
- method: 源自高质量网络教学视频,聚焦专业软件(PS/SD WebUI/PR/AE);分层评测:高层规划(无语言从视觉重建子任务流)→中层规划(视觉状态+目标生成动作叙述)→原子动作执行。
- training: **training-free**(以 GPT-4o 等评测)。
- data_exp: 网络教学视频+标注者复刻的规划流+录制动作;PS/SD/PR/AE。
- key_results: GPT-4o 在视觉中心 GUI 任务尤其高层规划很差。
- novelty: 首个教学视频派生、聚焦专业软件、三级分层评测的视觉中心 GUI 基准。
- one_line: 从教学视频建视觉中心 GUI 分层评测,揭示 GPT-4o 高层规划严重短板。

### [2508.14395] NoteIt: Converting Instructional Videos to Interactable Notes via Multimodal Video Understanding
- year/venue: 2025.08 / arXiv(HCI/系统)
- problem: 现有视频笔记工具无法全面保留信息、缺多样格式与交互。
- method: 流水线把教学视频自动转可交互笔记:视频解析→层级结构抽取→视觉关键信息抽取→笔记生成→UI 可定制(GIF 跟练版/精简版)。
- training: **training-free/未明**(多模态视频理解流水线)。
- data_exp: 技术评测数据集(规模未明)+用户研究 N=36。
- novelty: 教学视频→保留层级+多模态关键信息、可交互可定制的笔记系统。
- one_line: 把教学视频自动转可交互、可定制层级笔记(NoteIt)。

---

## C · 视频自监督分步/技能发现(最贴近"从操作视频去噪提技能")

### [2503.10684] Open-World Skill Discovery from Unsegmented Demonstration Videos (SBD)
- year/venue: 2025.03 / arXiv〔窗外·极对口〕
- problem: 开放世界在线演示视频长且未分段,难切分标注技能;现有靠随机切分或人工标注。
- method: 自监督把长视频切成语义感知、技能一致片段。受"事件分段理论"启发,Skill Boundary Detection(SBD):用**预训练无条件动作预测模型的预测误差**检测技能边界(误差骤升=技能切换);长度剪枝;片段用于训练条件策略+分层 agent。
- training: **自监督(annotation-free)分段**;下游用片段训练条件策略与分层 agent;有上下界证明。
- data_exp: Minecraft 海量 YouTube 游戏视频;Minecraft 技能 benchmark(短程原子/长程)。
- key_results: vs 随机分段:短程原子条件策略 +63.7%/+52.1%;长程分层 agent +11.3%/+20.8%。
- novelty: 首个免标注、用预测误差检测技能边界的学习型时序分段;直接用海量 YouTube 视频训 agent。
- limitations: 仅 Minecraft;依赖预训练动作模型与误差信号质量。
- one_line: 用动作模型预测误差自监督检测技能边界(SBD),把未分段长视频切成技能片段训 agent。

### [2304.13265] StepFormer: Self-supervised Step Discovery and Localization in Instructional Videos
- year/venue: 2023.04 / arXiv〔窗外·奠基〕
- problem: 教学视频步骤短而稀疏、大部分无关;key-step 定位需视频级人工标注,不可扩展。
- method: 无人工监督的 StepFormer:transformer decoder 用可学习 queries 注意视频,产出捕捉 key-steps 的 slot 序列;**仅用自动字幕(ASR narrations)做监督**,order-aware loss 过滤无关短语。
- training: **自监督**(字幕弱监督);order-aware loss;大规模教学视频训练。
- data_exp: 大规模教学视频;3 个 benchmark(step detection/localization);zero-shot 多步定位。
- key_results: 大幅超此前所有无/弱监督法;涌现 zero-shot 多步定位。
- novelty: 首个 transformer decoder+字幕 order-aware loss 的自监督步骤发现+定位。
- one_line: 仅用视频字幕自监督发现并定位教学视频步骤(StepFormer),大幅超弱监督。

### [2509.22019] EgoInstruct: Egocentric Video Dataset of Face-to-face Instructional Interactions with MLLM Benchmarking
- year/venue: 2025.09 / arXiv
- problem: 面对面教学场景是技能传承关键但 CV 未系统研究;缺数据集与分析技术。
- method: 新建第一人称"面对面教学"视频数据集,标注 procedural step segmentation+conversation-state classification;评测联合处理图/音/文的 MLLM 对比专用模型。
- training: **training-free 评测**(MLLM 无微调即超专用基线)。
- data_exp: 自采第一人称面对面教学视频+步骤分割/对话状态标注;规模未明。
- novelty: 首个面对面教学第一人称数据集+两基础任务+MLLM 基准。
- one_line: 首个面对面教学第一人称视频数据集,MLLM 无微调超专用基线。

---

## 附:数据资源(非论文,单列)
- **Ego4D / EgoExo4D**:最大第一人称(how-to)视频数据集(Ego4D 3700+ 小时);EgoExo4D 提供 ego+exo 同步视角。Ego4D Goal-Step 挑战=给未裁剪 egocentric 视频定位某 keystep 的 (start,end)。"操作视频→步骤/技能"的根基数据。
- 可扩备选(本轮未深读):ProMQA-Assembly、Causal-Plan-1M、GUI-World、GUI-ReWalk、Procedure-Aware Pretraining、MAGNET/SkillClaw/SkillGraph/WebXSkill。

---

## ★ 关键反面参照(后续加入)

### [2606.20363] Automating SKILL.md Generation for Computer-Using Agents via Interaction Trajectory Mining
- year/venue: 2026.06 / arXiv(**诊断/负面结果**)
- problem: 显式技能库便于检视,但"能否从交互数据挖出技能库、并真正提升下游策略"未知。
- method(三阶段,≈本项目 Step1+Step3 的 naive 版;**纯动作/文本,无视觉**):
  - **Phase1 轨迹分段(Skill Boundary Detection)**:用**相邻动作距离**当变点信号——Δa_t=‖a_t−a_{t-1}‖₂ > θ 处切边界;θ 在 held-out 上扫百分位、最大化边界 F1。动作向量=**15 维特征**(10 类原子动作 one-hot + 屏幕坐标 x,y + 归一化时间戳 + 截断文本长度 + 截断滚动量),**不用 DOM/截图/无障碍树/语言**。作者自承**会过度切分**(click→type、文本长度变化、坐标跳变都会误触发),并指出更优做法是 SBD 式预测误差(留待将来)。
  - **Phase2 技能嵌入(建库)**:每段用**动作向量的均值 μ + 对角方差 Σ** 概括(length-invariant **bag-of-actions**,**不保留段内顺序**)→ 用 **Wasserstein/Bures 距离聚类** → 每簇=一个候选技能 → 写成 SKILL.md。作者自承丢顺序损害可执行性(选→复制→粘贴的次序丢失)。
  - **Phase3 Skill-Aware GRPO**:Qwen3-8B 用 GRPO(无 SFT 暖启)在 1275 prompt(任务上下文+挖出的技能名)上训,配学习式轨迹奖励模型打分。
- training: **GRPO(无监督暖启)** + 学习式轨迹奖励模型。
- data_exp: GUI 交互轨迹(InteraSkill Workflows/IW);迁移评 WebArena/BrowseComp+/WorkArena-NLP/Mind2Web;4×H200。
- key_results(**负面**):挖出的簇**可读**(8 簇里 5 簇纯度≥0.95)但**不迁移**——GRPO 把 IW 技能步准确率仅 **18.5%→20.5%**,BrowseComp+ 几无变化,**还输给频率先验**。
- novelty: 自定性为**诊断研究**——轨迹挖掘能暴露可读技能结构,但**①边界检测器 ②无序段表示 ③离线奖励模型**都不足以可靠跨域提升策略。
- limitations: 纯动作特征(无视觉/DOM/语言)、bag-of-actions 丢序、离线奖励、boundary 过切。
- one_line: "动作跳变切段 + bag-of-actions 聚类成 SKILL.md + GRPO"的 naive 流水线,实证"可读≠有用、不迁移",点名三处病灶。
- **★ 与本项目关系**:它=mmskillrl 流水线的**纯文本/动作 naive 先行版且失败**;三处病灶正对本项目差异化——**多模态视觉技能**(它纯文本)/ **有序 interleaved**(它 bag-of-actions 丢序)/ **光标定位**(它动作跳变过切)/ **更好奖励**。最该认真对待的反面参照。
