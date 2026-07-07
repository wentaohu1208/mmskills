# GUI 轨迹 → 多模态 skill:跨轨迹归组 & 视觉复用 综述

> **问题**:我们做 `轨迹 → 多模态 skill`。skill 不该"一轨一条",而要**跨轨迹归纳**。但 skill 是多模态的:
> - **文字**能跨轨迹总结/合并;
> - **图片不能**(把多张截图"合并成一张 canonical 图"要靠 SOTA T2I 重生成,不现实)。
>
> 于是两个核心问题:
> - **Q1 归组**:GUI 轨迹里,靠什么判断"哪些属于同一种 skill",从而归纳?
> - **Q2 视觉**:归组后,skill 的**视觉部分**怎么处理(合并 / 留一张代表 / 留多张 exemplar+检索 / 抽成文字 / 丢弃)?
>
> 本文基于 **70+ 篇** agent-skill + GUI-agent 论文(6 组并行深读,arXiv ID 均交叉核验)。**结论先行**见 §1。

---

## 1. 结论先行(TL;DR)

**文字与图像两个通道必须"分治":文字跨轨迹归纳/合并,图像绝不合并 → 选真实代表帧(medoid/exemplar)+ 多模态检索。**

1. **归组(Q1)不靠图,靠文本/动作代理**:先给每条轨迹反推 intent 文本(OS-Genesis 式)→ 按 **intent/task embedding 聚类 + 按 app 分桶**(AWM 式)→ 桶内让 LLM 抽"**反复出现的动作子序列**"蒸馏成命名 skill。判"同一种"用 **task/子目标/状态条件相似 + VLM judge**,不用像素聚类。
2. **图像(Q2)= 选真实代表帧,禁止合并**:对每个关键状态,从组内轨迹**选 medoid/exemplar 真实关键帧**(可多视角:full / focus-crop / before / after),**绝不合成平均图**。
3. **文字通道可放心抽象**:procedure、state card、when-to-use/verification、变量化 workflow —— 文字是**唯一可合并/变量化**的通道。
4. **apply-time = 检索最近邻**:每个 skill 留**多张**真实 exemplar 帧,运行时按 live 截图的视觉相似度检索并对齐,而非塞一张固定图。

**全 70+ 篇里,做"真正跨轨迹归组"的与"在 skill 里留真实像素"的,几乎从不同时成立;且零篇合并图像。** 二者兼得(**跨轨迹归组 + 人可读关键帧**)= 本项目的空白点。最接近的现成基线 = **MMSkills `2605.13527`**(与本项目同题)。

---

## 2. Q1:如何判断"同一种 skill"(归组机制,能力四档)

| 档 | 机制 | 判"同一种"的信号 | 代表作 |
|---|---|---|---|
| **① 真·批量抽象**(N 条一起喂,抽公共/对比) | 把同桶多条轨迹拼进一个 prompt,LLM 抽公共子例程;或正负对比归纳 | **复现的动作子序列 / 共享子目标 / 状态条件对比** | **AWM** `2409.07429`、**AutoGuide** `2403.08978`(分叉点+状态条件)、W2S `2606.06893`(结构对齐+分支调和)、ExpeL `2308.10144`、AutoManual `2405.16247` |
| **② 逐轨迹归纳 + 库层去重** | 一轨→一 skill/API,靠执行验证或新颖性提案避免重复 | **程序化可复用性(重放仍成功)/ 函数名去重** | **ASI** `2504.06821`(re-execution 验证)、**SkillWeaver** `2504.07079`、TroVE `2401.12869`(grow&trim)、ReGAL `2401.16467` |
| **③ 检索式 exemplar** | 不离线合并,查询时按相似度取 top-k | **task/多模态 embedding 相似度** | **Synapse** `2306.07863`、WILBUR `2404.05902`、ExpeL(kNN)、**JARVIS-1** `2311.05997`(两级检索) |
| **④ 无跨轨迹归纳(反例)** | 只有单任务内反思 / 经验压进权重 | — | WebPilot `2408.15978`、AutoWebGLM `2404.03648`、Voyager `2305.16291`(一任务一 skill) |

**给 OSWorld 的最实用配方**(文献一致收敛):
1. **补 intent** —— 原始轨迹先 reverse task synthesis(OS-Genesis `2412.19723` / Learn-by-Interact `2501.10893` 的 backward construction)反推 NL 意图并清洗;
2. **一级粗聚类(文本主键)** —— intent embedding + kNN/聚类(KATE `2101.06804`、Dial-In `2412.09049` 的"embedding 聚类 + LLM-in-loop 精修命名"),按 app/域分桶(AWM);判"同类"建议用 **EPR `2112.08633` 的效用视角(是否共享同一成功动作模式)**、**ActionBert `2012.12350` 的理念(用动作而非外观定义同类)**;
3. **二级细归纳** —— 桶内 LLM 抽重复动作子序列蒸馏成命名 skill(AWM/SkillWeaver),坐标/具体值抽象成占位符(呼应我们 schema「坐标不进 skill」),用**重放验证**(ASI)守门;
4. **合并判据** —— 两条经验算不算同一 skill,用 **HyMEM `2603.10291` 的 ADD/MERGE/REPLACE + VLM judge**(比对任务描述/动作序列/视觉上下文)。

> **为什么归组不能只用纯文本键**:纯文本键无法按视觉召回(Agent S 的局限)。建议用**图文联合 embedding** 作键(RA-CM3 `2211.12561`、Auto-scaling Continuous Memory `2510.09038`),视觉在密集小控件/同名不同页时做**二级消歧**。

### 2.1 "两条经验算不算同一个 skill"—— 判等/合并判据(五档)

skill-RL/技能库方向 22 篇的核心教训:**"库怎么长大"人人做,"怎么判两个 skill 是同一个并合并"几乎空白**——大多数只 append + 一句 prompt "别生成重复的"。

| 档 | 判等/合并做法 | 代表作 |
|---|---|---|
| ① 不判等,纯 append + prompt 软约束 | Voyager · AWM · SkillWeaver `2504.07079` · ASI `2504.06821` · SkillRL `2602.08234` · BOSS `2310.10021` |
| ② 只按利用率剪枝,不合并 | TroVE(频率 `½log₁₀n`)· Skill1 `2605.06130`(`U·log n`)· SLIM `2605.10923`(边际贡献+最小曝光)· SKILL0 `2604.02268`(`Δ=有它−没它`)· SkillMaster `2605.08693`(K=4 反事实 probe) |
| ③ 靠结构/正交性回避重复 | Eigenoptions `1703.00956` · Option-Critic `1609.05140` · HAM·MAXQ `cs/9905014` |
| ④ 压缩式合并(需可符号对齐到语义等价) | DreamCoder `2006.08381`(refactor→MDL)· LILO `2310.19791` · Stitch `2211.16605` |
| ⑤ **显式判等 + 合并(直接可迁移)** | **SkillGraph `2605.12039`**(邻居 Jaccard≥0.85→LLM 综合)· **LOTUS `2311.02058`**(DINOv2 视觉聚类+Silhouette 阈值)· **Mem0 `2504.19413` · ExpeL**(召回→LLM 判 ADD/UPDATE/DELETE) |

**给我们的三条可迁移范式(⑤ 档)**:
- **Mem0/ExpeL 两阶段** ← 主骨架:先 embedding **粗召回** top-s 相似候选 → 再 VLM/LLM **精判 ADD(新增)/ UPDATE(合并)/ DELETE(剪枝)/ NOOP**,无硬阈值。
- **LOTUS 视觉判等**:在 **DINOv2 / UI 视觉特征**上增量聚类 + Silhouette 阈值(高于→并入、低于→新建)—— 视觉只用于**召回/判等**。
- **MAXQ funnel + SkillGraph**:两 skill 若把不同起点**漏斗到相同结果状态**、或**共享大部分上下文邻居**,即视作等价 —— GUI 应按**"达成的结果状态 / 共现上下文"判等**,**截图差异正是要漏掉的无关变量**。

> **铁律**(与 §3/§4 一致):判等/召回**可以**用视觉,但**合并只作用于 skill 的抽象描述 / 程序化 intent / 动作序列 / 结果状态,截图绝不合并**;剪枝用利用率(成功率 + 使用次数,如 SkillGraph 的 `n_use≥20 且成功率<0.15` deprecate)。

---

## 3. Q2:视觉通道怎么处理(五类策略,及"零篇合并图")

把 70+ 篇按"实例不同时视觉怎么存"排开:

| 类 | 策略 | 代表作 | 评价 |
|---|---|---|---|
| **(i) MERGE 合成 canonical 图** | 把多张示范合并/平均成一张 | **零篇** | 无人做——负面共识 |
| **(ii) 留一张代表帧** | 单 medoid/exemplar | MMSkills(部分)、VisualSkill `2606.18448` | 退化选择,单张难覆盖多实例 |
| **(iii) 留多张 exemplar + 检索** | 多真实帧 + 视觉/多模态 embedding 最近邻 | **Optimus-1 AMEP** `2408.03615`、**MementoGUI ROI-crop** `2605.18652`、**Auto-scaling Continuous Memory** `2510.09038`、JARVIS-1、RAP `2402.03610` | **✅ 推荐主线** |
| **(iv) 抽成文本** | 元素文档 / a11y / caption / marks / 变量化 | AppAgent `2312.13771`、AWM、AutoGuide、Agent S `2410.08164`、UI-Mem `2602.05832`、ICAL construals `2406.14596` | 主流但**丢像素语义**(见 §4 数字) |
| **(v) text-only / 压进权重 latent** | 丢视觉 / 端到端摊进参数 | OS-Copilot `2402.07456`、Cradle `2403.03186`、CogAgent `2312.08914`、Optimus-2 `2502.19902`、HyMEM(视觉是隐式 latent) | 不可读/不可编辑/不可审校 |

**核心事实**:
- **没有任何一篇合并图像**;唯一"融合"的 SegGPT `2304.03284` 也只在 **feature/输出级**对真实示范对集成,不合成假 exemplar。
- 真正**留真实像素**的极少数(Optimus-1、MementoGUI、Auto-scaling Continuous Memory、GUI-Odyssey `2406.08451`),清一色走 **(iii) 选代表帧 + 检索**,不合并。
- **"跨轨迹归组(Q1①)"与"留真实像素(Q2 iii)"几乎从不同时成立**:批量归纳者(AWM/W2S)全是纯文本;真正留图者(ICAL/MMSkills/VisualSkill)在跨轨迹归组上偏弱。→ 二者兼得 = 空白点。

---

## 4. 为什么"选真实代表帧"而不是"合成一张"(理论 + 数字)

**方法论骨干(选真实点 vs 合成平均)**:
- **k-medoids / PAM**(Kaufman & Rousseeuw 1987/1990):簇中心 = **medoid = 真实成员**,鲁棒、支持任意距离、在"均值无意义"(离散/结构化/非欧对象)时仍可用。
- **Affinity Propagation**(*Science* 2007):message passing 从**真实点**选 exemplar,从不造人工中心。
- **VSUMM**(*PRL* 2011):视频关键帧标准做法 = 聚类后**把合成均值 snap 回最近的真实帧**(平均帧是无意义模糊)。
- **Prototypical Networks** `1703.05175`(边界反例):合成均值(centroid)**只在**"学到的度量 embedding 空间做分类"时安全;它**无法展示/回放**。→ **凡是 skill 里要展示/回放/审校的图,必须是真实帧;latent 平均只能用于检索打分**。

**经验数字(抽成文字会掉分)**:
- **VisualSkill `2606.18448`** 的 text-only 消融:多模态 **0.456** → 纯文字 **0.373**(**−8.3 绝对分**)。原文:"许多 UI 元素用文字描述冗长/歧义,text-only 与 computer-use 环境是 poor match"。
- 结论链:合成假图 = centroid,失鲁棒 + 对不可展示对象无意义(方法论);连降级到文字都掉 8.3 分(经验);全 cluster 零篇采用(共识)。**三重证据 → 图像通道绝不走 T2I 合成。**

---

## 5. 与本项目的关系:基线、空白点、落地方案

**直接基线 = MMSkills `2605.13527`**(同题,与 mmskillrl 对标):
- 四步流水线:**workflow grouping → procedure induction → visual grounding → meta-skill-guided auditing**;
- 产物 = multimodal skill package = **文本 procedure + runtime state cards + 多视角 keyframes**(full/focus-crop/before/after);
- apply-time 临时 branch 里"选并对齐 multimodal evidence"与 live 截图对齐 —— **正是我们要复现/超越的靶心**。

**空白点(= 我们的贡献位)**:**显式可复用的多模态 skill 单元(真正跨轨迹归组)+ 人可读关键帧**,二者兼得——全谱系无一篇做到。

**落地方案(把各组算子拼起来)**:

```
① 补 intent   : 每条轨迹 reverse-synth 出 NL 意图并清洗           (OS-Genesis / backward construction)
② 归组(文本键): intent embedding 聚类 + 按 app 分桶               (AWM / Dial-In / EPR 效用视角)
③ 文本诱导    : 桶内 LLM 抽重复动作子序列 → procedure + state card  (AWM / SkillWeaver;坐标→占位符)
④ 视觉挑帧    : 每个关键状态从组内选 medoid/exemplar 真实帧(多视角) (Optimus-1 AMEP / VSUMM;禁合并)
             + 关键视觉判据额外语言化                              (ICAL construals)
⑤ 判等合并    : 粗召回(视觉/结构邻居)→ VLM judge 精判 ADD/UPDATE/DELETE  (Mem0/ExpeL 两阶段; 合并在 intent/结果层, 截图不合并; MAXQ funnel 按结果状态判等)
⑥ 入库验证    : 重放验证(重放仍成功 + 确用到该 skill + 确改环境)    (ASI re-execution;视觉版需 VLM judge)
⑦ apply-time  : 留多张 exemplar 帧,按 live 截图视觉相似度检索对齐    (MementoGUI ROI + Auto-scaling CM: CLIP+FAISS)
```

**一句话**:**归组走文本/动作(intent 聚类 + LLM 抽公共子序列),视觉走"选真实代表帧 + 多模态检索",两通道在 skill 内绑定但各用各的复用机制** —— 这正是 MMSkills / VisualSkill / Optimus-1 / Auto-scaling Continuous Memory 共同收敛到的设计。

---

## 6. 论文索引(按组,arXiv ID 均核验)

**① 技能库与归纳(embodied/code/general)**:Voyager 2305.16291 · JARVIS-1 2311.05997 · GITM 2305.17144 · DEPS 2302.01560 · Odyssey 2407.15325 · ExpeL 2308.10144 · Cradle 2403.03186 · ADAS 2408.08435 · Agent-Pro 2402.17574 · AutoGuide 2403.08978 · CodeAsPolicies 2209.07753 · LEAP 2410.05434 · Reflexion 2303.11366 · AWM 2409.07429 · TroVE 2401.12869 · ReGAL 2401.16467 · Optimus-1 2408.03615 · PolySkill 2510.15863

**② 跨轨迹 workflow/skill 归纳(web/gui,最对口)**:AWM 2409.07429 · W2S 2606.06893 · ExpeL 2308.10144 · AutoGuide 2403.08978 · AutoManual 2405.16247 · ASI 2504.06821 · SkillWeaver 2504.07079 · Learn-by-Interact 2501.10893 · NSI 2605.01293 · ReUseIt 2510.14308 · Synapse 2306.07863 · WILBUR 2404.05902 · ICAL 2406.14596 · Visual-Skills(position) 2606.01414 · VisualSkill 2606.18448 · **MMSkills 2605.13527** · WebPilot 2408.15978 · AutoWebGLM 2404.03648

**③ GUI 记忆(多模态)**:AppAgent 2312.13771 · AppAgent-v2 2408.11824 · Mobile-Agent-E 2501.11733 · Mobile-Agent-v2 2406.01014 · Mobile-Agent-v3/GUI-Owl 2508.15144 · Mobile-Agent 2401.16158 · CoCo-Agent 2402.11941 · OS-Copilot/FRIDAY 2402.07456 · UFO 2402.07939 · UFO2 2504.14603 · AssistGUI 2312.13108 · Agent-E 2407.13032 · OSCAR 2410.18963 · SeeAct 2401.01614 · WebVoyager 2401.13919 · GUI-Odyssey 2406.08451 · Optimus-2 2502.19902 · **HyMEM 2603.10291** · UI-Mem 2602.05832 · **MementoGUI 2605.18652** · Darwinian Memory 2601.22528

**④ 轨迹/UI 表示 · 相似度 · 聚类 · 检索**:Screen2Vec 2101.11103 · UIBert 2107.13731 · ActionBert 2012.12350 · Spotlight 2209.14927 · Lexi 2301.10165 · UIClip 2404.12500 · GUing 2405.00145 · Ferret-UI 2404.05719 · Ferret-UI-2 2410.18967 · UGround 2410.05243 · SeeClick 2401.10935 · CogAgent 2312.08914 · OmniParser 2408.00203 · OSWorld 2404.07972 · RAP 2402.03610 · KATE 2101.06804 · EPR 2112.08633 · Dial-In 2412.09049

**⑤ 多模态 exemplar/检索 + 方法论骨干**:MMSkills 2605.13527 · VisualSkill 2606.18448 · Mirage-1 2506.10387 · **Auto-scaling Continuous Memory 2510.09038** · Agent S 2410.08164 · Agent S2 2504.00906 · What-Makes-Good-Examples 2301.13670 · Prompt-SelF 2304.04748 · SegGPT 2304.03284 · Painter 2212.02499 · RA-CM3 2211.12561 · MMICL 2309.07915 · RAICL 2505.02087 · SoM 2310.11441 · VipAct 2410.16400 · ICAL 2406.14596 · Prototypical Networks 1703.05175 · k-medoids/PAM(Wiley 1990) · Affinity Propagation(Science 2007) · VSUMM(PRL 2011) · RESOURCE2SKILL 2606.29538

**⑥ Skill-RL 进化 + 技能库判等/去重/剪枝(见 §2.1)**:SkillRL 2602.08234 · Skill1 2605.06130 · Skill-R1 2605.09359 · SkillMaster 2605.08693 · SKILL0 2604.02268 · **SkillGraph 2605.12039** · SLIM 2605.10923 · Voyager 2305.16291 · AWM 2409.07429 · TroVE 2401.12869 · SkillWeaver 2504.07079 · ASI 2504.06821 · ExpeL 2308.10144 · **LOTUS 2311.02058** · **Mem0 2504.19413** · DreamCoder 2006.08381 · LILO 2310.19791 · Stitch 2211.16605 · Option-Critic 1609.05140 · Eigenoptions 1703.00956 · HAM·MAXQ cs/9905014 · BOSS 2310.10021 · SkillMimic 2408.15270 · ELLM 2302.06692

> **总计 90+ 篇**(六组去重后)。待核 venue:ASI(COLM'25?)、Learn-by-Interact(ICML'25?)、Agent S/S2 会议为报告值;MMSkills/VisualSkill/HyMEM/MementoGUI/SkillGraph 等 2026 新作正式引用前再核 DOI。"CIL" 用户所指未定:LOTUS `2311.02058`(最可能)/ 备选 IsCiL `2410.22658`、SPECI `2504.15561`(待确认)。skill-RL 5 篇的结构化深读另见 memory `reference_agent_skill_rl_survey`。
>
> **补充参考**:RESOURCE2SKILL `2606.29538`(人写多模态资源→可执行技能 Wiki;一源一 skill、**不跨轨归纳**,与我们互补)—— 独立印证本文两条主张:**留真实帧+按需加载视觉**(视频源消融 −9.2 / 视觉模态 +1.9)、**BM25+LM 层级检索 > dense(+8.9)**,可作 §3/§4/Phase 3 的旁证。
>
> **同路工程产品**:Skill-Omni(openJiuwen / JiuwenSwarm)——《让 Skill "有图可依":openJiuwen 首发多模态 Skill 范式 Skill-Omni》 https://www.qbitai.com/2026/07/445229.html(网页/视频教程 → 多模态 skill,去噪留"前后对比图"+ 按需读取;与 RESOURCE2SKILL 同路:**一源一 skill、不跨轨归纳**,引 MMSkills/VisualSkill 血统)。
>
> Skill-Guided Continuation Distillation for GUI Agents `2606.18890` https://arxiv.org/abs/2606.18890
