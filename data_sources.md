# 数据源清单 — 从视频/轨迹抽取多模态 agent skill(static + interleaved)

> 配套 `research_result_video2skill.md` / `paper_list_video2skill.md`。用途:Step 2"从视频抽技能"选数据。
> 选数据两条核心判据:**① 有无原始视频/轨迹(抽取的输入);② 有无"关键位置"监督(cursor坐标 / 动作 / keystep边界 / 手部姿态)——决定"定位关键位置"能否免标注**。
> 标 ★ = 对本项目最对口的"金标"。

---

## A. GUI — 桌面(最贴 MMSkills 主线)
| 数据源 | 形态 | 规模 | 关键位置监督 | static/interleaved 适配 |
|---|---|---|---|---|
| ★ **CUA-Suite / VideoCUA** (2603.24440) | **连续 30fps 录屏 + 运动学光标轨迹 + 每步~497词推理标注** | ~55h / 600万帧 / ~1万任务 / 87应用;配 GroundCUA(56k截图,360万UI元素) | **光标轨迹=天然关键位置金标**;每步标注 | **两者皆佳**:cursor点→static参考区;每步截图→interleaved |
| **OSWorld / macOSWorld** | 桌面任务 + 截图轨迹(执行式) | OSWorld 361任务/10域 | 动作(pyautogui)坐标 | 你已有 MMSkills 技能库+映射;可直接产 interleaved |
| **Video2GUI** (2605.14747) | 视频→交互轨迹(合成) | 大规模 | 合成动作 | 视频→轨迹的现成管线 |
| **OS-Genesis** (2412.19723) / **Anchor** (2602.07153) | 合成桌面轨迹(逆向任务/分支点) | — | 动作 + TRM/verifier | 偏数据合成,可补样本 |

## B. GUI — Web
| 数据源 | 形态 | 规模 | 关键位置监督 | 适配 |
|---|---|---|---|---|
| ★ **TongUI / GUI-Net-1M** (2504.12679) | 网页教程(视频+图文)→GUI轨迹,**抽 salient frame 当每步截图** | **100万轨迹 / 5 OS / 280+应用** | ASR/captioning→步骤;每步截图 | interleaved 现成(步骤↔截图);规模最大 |
| **AgentTrek** (2412.09605) | 教程→轨迹,**含截图+视频录制+DOM** | 大规模 | 步骤指令 + DOM元素 | DOM给精确元素框→static定位准 |
| **Mind2Web / MM-Mind2Web** | 真实网页任务 + 人类演示轨迹,HTML对齐截图 | 2000+任务 / 137站 | 动作元素(HTML)+ 截图 | static(元素框)+ interleaved(步↔截图) |

## C. GUI — 移动
| 数据源 | 形态 | 规模 | 关键位置监督 | 适配 |
|---|---|---|---|---|
| **AndroidInTheWild (AitW)** | Android 人类演示 | **71.5万演示 / 3万指令** | 触摸/手势坐标 + 截图 | 触点=关键位置;规模大 |
| **GUI-Odyssey** | 跨app移动导航,人类演示 | 7735 episode / 201应用 / 平均15+步 | 动作 + 截图(每步) | 长流程→interleaved 好素材 |
| **AndroidControl** / **OmniGUI**(2605.18758,含音频/视频) | 移动控制轨迹 / 全模态步级 | OmniGUI 709演示/2579步 | 动作 + (OmniGUI还有音频/视频) | OmniGUI 适合多模态 interleaved |

## D. 游戏(MMSkills/SBD 的 game 战场)
| 数据源 | 形态 | 规模 | 关键位置监督 | 适配 |
|---|---|---|---|---|
| ★ **SBD 的 Minecraft YouTube** (2503.10684) | **海量未标注游戏视频**(自监督切技能) | YouTube规模;OpenAI contractor 1000h/68M帧→13万切片 | **无需标注**(预测误差切边界)+ IDM补动作 | 验证"从原始视频自监督切技能"的现成范式 |
| **VAB-Minecraft**(VisualAgentBench) | Minecraft agent 任务 | — | 动作 | MMSkills 在此证过技能有用 |
| **Super Mario Bros**(MMSkills用) | 游戏 | — | 动作/奖励 | 游戏类补充 |

## E. 具身 / 机器人操作(AtlasVA 的域,非 GUI)
| 数据源 | 形态 | 规模 | 关键位置监督 | 适配 |
|---|---|---|---|---|
| ★ **Open X-Embodiment (OXE)** | 真机操作轨迹(视频+动作) | **100万+轨迹 / 22本体 / 527技能** | 末端/关节动作 + 语言 | static=物体/区域;interleaved=阶段↔帧;规模巨大 |
| **DROID** | 真机 in-the-wild 操作 | 7.6万演示 / 350h / 564场景 / 86任务 | 动作 + 语言指令 | 场景多样,泛化好 |
| **BridgeData V2** | 多任务操作 | 6万+轨迹 / 13技能 / 24环境 | 动作 | 经典模仿/扩散策略数据 |

## F. Egocentric / 教学 how-to(物理世界"操作视频"根基)
| 数据源 | 形态 | 规模 | 关键位置监督 | 适配 |
|---|---|---|---|---|
| ★ **Ego-Exo4D** (2311.18259) | **第一+第三人称同步**技能活动视频 | **1286h / 5035 takes / 43任务 / 689 keysteps / 8域** | **keystep边界 + 3D手/身姿态 + 流程依赖 + 熟练度** | 手/物位置=关键位置;keystep↔帧=interleaved;**标注最全** |
| **Ego4D** | 第一人称 how-to | 3700h+ | Goal-Step:keystep (start,end) | 海量;切步骤 |
| **HoloAssist / EPIC-KITCHENS / Assembly101** | 第一人称程序活动 | 各异 | 动作/步骤标注、手物交互 | 装配/厨房程序;interleaved 好 |
| **HowTo100M** | 旁白教学视频(弱监督) | **136M片段 / 122万视频 / 23k任务** | **ASR 旁白(弱标注)** | 超大规模、免人工;StepFormer 式弱监督 |
| **COIN / CrossTask / YouCook2 / HT-Step** | 教学视频 + 步骤标注 | COIN 万级/180任务;YouCook2 2000视频 | 步骤时间区间 + 文字 | 步骤边界现成→interleaved/分步 |
| **EgoInstruct** (2509.22019) | 面对面教学第一人称 | — | 步骤分割 + 对话状态 | 教学交互 |

---

## 跨域:谁自带"关键位置"监督(对 Step 2 定位最省事)
- **像素级点位(最直接)**:CUA-Suite(光标轨迹)★、AitW/GUI-Odyssey(触点)、Mind2Web/AgentTrek(HTML/DOM 元素框)。
- **手/物 3D 位置**:Ego-Exo4D(3D 手姿态)★、EPIC-KITCHENS(手物交互)。
- **机器人动作位姿**:OXE/DROID/BridgeData(末端执行器轨迹)。
- **只有时间步、无空间点**:HowTo100M/COIN/YouCook2(只步骤边界)→ 空间关键位置仍需 grounding 补。
- **无标注(自监督)**:SBD/Minecraft YouTube(预测误差切边界)★。

## static vs interleaved 各自最优数据
- **static(固定参考图:控件/物体)**:GUI 选 **AgentTrek/Mind2Web**(DOM元素框精确)或 **CUA-Suite**(光标点);机器人选 OXE(物体框)。
- **interleaved(步骤↔证据帧)**:任何"每步配截图/帧"的都行——**TongUI、GUI-Odyssey、Ego-Exo4D(keystep)、COIN/YouCook2(步骤区间)** 最现成。

## MVP 推荐组合(从易到难)
1. **GUI 桌面起步(最对口你的线)**:★ **CUA-Suite/VideoCUA**(光标轨迹免标注定位 + 每步截图)→ 抽 static(光标点周围控件)+ interleaved(步骤↔截图);在 **OSWorld** 上验证"用"。
2. **加 Web 规模**:TongUI/GUI-Net-1M(百万)补样本。
3. **跨域验证泛化(非 GUI)**:Ego-Exo4D(物理操作,keystep+手姿态)证明"视频→skill"不限 GUI;或 OXE(机器人)。
4. **自监督切分参考**:SBD/Minecraft YouTube 范式(从原始视频无标注切技能边界)。
