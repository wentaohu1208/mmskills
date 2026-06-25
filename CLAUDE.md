# mmskillrl — 多模态 agent skill:结构定义 + 四步适配

> **设计版本 v10 · 更新时间 2026-06-26**(v10:**AgentNet 提取方案定为 b-full**——VLM 管语义(切分/情境/锚点命名)+ 真实 `value.code` 管 procedure + 新增 VLM 加工(清洗噪声+按灵活度参数化)+ anchor 用"红点法"(真实点钉中心+VLM 框边界+四档兜底);小元素 bbox 已解决(原已知待解④了结),依据 65 篇调研选 b(见 §7)。v9:**数据源转向 AgentNet Ubuntu**——VideoCUA 实测是跨 OS(mac+Win)杂数据、刷不了 OSWorld;改用 `xlangai/AgentNet` 的 Ubuntu 子集(~5K,MMSkills 同源、对齐 OSWorld GNOME);VideoCUA 退为方法论验证(见 §7 末)。v8:§2 加 `state`(mode/precondition/state_anchor),26 skill 触发 ~86%;v7:切分准则(检索 80%→100%)+ name 英文 + 规则后处理;v6:提取流程跑通;v5:两种视觉粒度。本文件即最新设计;以后认顶部时间取最新)。
> 接续先读本文件 + 同目录 `research_result_video2skill.md`(综述)、`data_sources.md`(数据源)、`paper_list_video2skill.md`(逐篇 notes,末尾有反面参照 2606.20363)。

## 0. 当前目标(聚焦)
两件事,**别的先不碰**:
1. **定义"多模态 agent skill"的结构(三层)**。
2. **解决四步:检索 → 触发 → 对齐 → 执行——多模态 agent ↔ 多模态 skill 怎么适配**(核心:每步让 agent"当前看到的画面"真正用上,不退回文字 caption)。
- **域**:GUI(精确,像素级)+ Visual Game / Minecraft(粗,物体/区域级),一精一粗证通用。
- **接下来(要试验)**:**从视频自动提取多模态 skill**(见 §7)。
- **暂缓**:RL、技能进化/管理(后续)。

## 1. 动机:文字 skill 不够(四个失败模式)
视觉 agentic 任务里当前画面很重要,文字 skill 把视觉压没,导致四步全坏:
- **检索**:agent 的 query 本质是"它看到的画面",文字 skill 只能按文字检索 → 模态对不齐,视觉信号浪费,退回 caption。
- **触发**:即使检索到,也无法精确核验"我现在真在这个 skill 假设的状态吗" → 错时机触发。
- **对齐**:文字步骤说不清"这步该看哪块、目标长啥样"。
- **执行**:步骤缺"步骤↔视觉证据"绑定 → 执行错位。

## 2. ★ 多模态 skill 的结构(三层定义)
一句话直觉:**一个 skill = 带视觉的"情境剧本" = 情境(何时用)+ 锚点(关键元素长啥样/怎么找)+ 流程(每步做啥/应变成啥)**。每层**文字 + 视觉成对**,**用 `role` 名字互相绑定**(文字管语义,视觉管"认得出/找得到/对得上")。

### 第 1 层 · 情境 Context(WHEN)→ 服务 ①检索 ②触发
这个技能的"情境指纹":判断"现在该不该用、能不能被召回"。
| 字段 | 模态 | 内容 |
|---|---|---|
| `goal` | 文字 | 这技能干啥(也帮检索:任务语义) |
| `cues` | 文字 + 视觉 | 文字:判别线索(看哪几点判断"在不在此状态");视觉:**整帧**(整体场景截图)——情境管"整体识别"、看整个画面格局,**不裁局部**(泛化靠 VLM 抓格局而非死记像素) |
| `state` | 文字 + 视觉 | **触发硬条件**(判"该不该用"的判别条件,区别于 cues 的"整体场景描述"):`mode`(当前工具栏/编辑模式;游戏导航填 null)+ `precondition`(触发前画面须满足的前置态——GUI 如 `on_page_3`/`text_selected`/`dialog_open`、game 如 `at_entrance`/`facing_target`/`holding_axe` 等**空间前置**)+ `state_anchor`(画面里【能确认状态】的局部:页码框/状态栏/模式标——**读状态用,≠第2层操作锚点,不进 procedure**) |
| `sig` | 视觉嵌入 / 文字嵌入(**两路分开**) | 由 cues + state 预计算的检索签名 |
- **关键决策**:① cues=**整帧(整体场景)+ 文字判别线索**(情境管"整体识别"、看整个画面格局;与第 2 层锚点的"局部裁剪"是**两种视觉粒度**);② `sig` **视觉、文字分两路 embedding,不融合**——**视觉那路保持"图↔图"直比、不经文字 caption**(这正是"检索别浪费视觉"的解法);检索 = 两路分别算相似度再合(加权 或 视觉召回→文字 rerank);③ 视觉编码器与第 2 层"对齐"**共享同一套**;④ **`state` = 触发的硬条件**(`cues` 描述"整体场景",`state` 给"模式/前置"这种**判别条件**):`mode`+`precondition` 是文字(判逻辑)、`state_anchor` 是视觉(去画面哪读状态);**`state_anchor` 是"眼看·判时机",≠ 第 2 层 anchors 的"手碰·做操作",不进 procedure**;`precondition` 常 = **上一个 event 的 `expect`**(视频连续、白送且可校验)。**按域可选**:GUI 三件全;game 导航 `mode` 多为 null、`precondition` 是空间前置、`state_anchor` **并入 `space:世界` 锚点**(别另造独立的)——避免给 game 套 GUI 包袱。

### 第 2 层 · 锚点 Anchors(WHERE)→ 服务 ③对齐
技能"会动到/会看的那几个关键元素"的注册表。每个锚点:
| 字段 | 模态 | 内容 |
|---|---|---|
| `role` | 文字 | 语义角色名(`save_button`/`target_tree`)——**绑定键**:第 3 层靠它引用,文字视觉靠它对齐 |
| `appearance` | 视觉 + 嵌入 | 参考外观裁剪(对齐时图↔图区域匹配,与 `sig.visual` 同编码器) |
| `locator` | 文字 | 怎么找——相对地标/语义描述,**可含相对其他锚点的空间关系**(如"在取消键右边") |
- **关键决策**:① **不存坐标!** 只存"可重定位描述"(外观+locator),坐标在③对齐时**拿当前屏现算输出** → 跨实例复用;② 允许"锚点图"(相对关系)消歧;③ 游戏可加 `space`:**世界**(树,随转视角在画面里移动)/ **屏幕**(快捷栏格子),GUI 永远屏幕;④ **anchors 只放"要操作/对齐的元素"**(要点的按钮、要输入的框、要瞄准的物体)——**动作产生的结果/核验**(插入后的控件、变化的页码)归 §3 procedure 的 `expect`,**不当锚点**(否则会塞入裁不准的小元素);⑤ **(v10)AgentNet 域用「红点法」生成锚点**:真实 `click_xy` 钉中心、VLM 框边界,字段含 `click_xy`/`bbox_source`(`vlm_box` 或三种 fallback);只 `click` 类有 anchor,`type`/`press`/`hotkey` 纯键盘步无 anchor(见 §7)。
- **对齐机制** = `appearance` 嵌入 ↔ 当前屏各区域匹配 + `locator` 文字消歧 → 输出"它现在在 (x,y)/这块"。

### 第 3 层 · 流程 Procedure(HOW)→ 服务 ④执行(+核验)
**线性**(不做条件分支)。有序步骤,每步:
| 字段 | 模态 | 内容 |
|---|---|---|
| `action` | 文字 + 结构 | 动作类型 + 作用锚点(**by `role`,不写坐标**) + 可选参数。例:`click(save_button)`、`type(filename_field,<text>)`、`attack(target_tree,长按)`(**取值用占位符,不写死实例值**,见关键④) |
| `expect` | 视觉(+文字) | 做对后画面应变成啥——即**核验**;**也兼"持续动作的停止条件"**(如"长按直到木头+1") |
- **关键**:① 步骤**只用 role 引用锚点**,坐标来自②对齐;② **图不内联在流程里**(图在第 2 层),靠 role 引用 → 运行时才展开成图文交错(见 §4);③ `expect` 统一表达原子动作(核验)与持续动作(停止+核验);④ **取值参数化**:`input/type/select` 等动作的"具体取值"用占位符(`input(field,<text>)`、`select(menu,<option>)`),**不写死这次的实例值**(`"t"`/`"report"`/某文件名)——值是**任务参数**,运行时才由任务填(`<text>`→`"report"`);`click(role)` 无取值,天然可复用。**(v10)AgentNet 域**:procedure 由真实 `value.code` 生成、每步存 `raw`;参数化升级为 **VLM 按 goal 灵活度**(保留命令骨架、只挖可变值,如 `touch <file>` 而非整体 `<text>`),替代纯规则后处理;清洗掉的噪声步入 `dropped_steps` 留档(见 §7)。

## 3. 三层 ↔ 四步,及三组易混概念
| 层 | 服务哪步 |
|---|---|
| ① 情境 Context | ① 检索 + ② 触发 |
| ② 锚点 Anchors | ③ 对齐 |
| ③ 流程 Procedure | ④ 执行(+核验) |

- **触发 vs 对齐 = 认出来 vs 找位置(what vs where)**:触发=识别"我在不在这个态"(是非);对齐=定位"元素在当前屏哪"(坐标)。**概念分开,实现上可并成"一次视觉匹配同时给适用性+位置"**(MMSkills 即如此)。
- **第 1 层 vs 第 2 层**:Context=**整体场景识别**(决策"用不用/哪个");Anchors=**局部元素定位**(测量"在哪")。视觉上会重叠(Minecraft 里"前方有树"≈ `target_tree`),但**用途不同**:一个拿来决策,一个拿来定位。**→ 视觉粒度也不同:Context 存【整帧】(整体识别),Anchors 存【局部裁剪】(单元素定位)。**
- **`state_anchor` vs `anchors` = 眼看 vs 手碰**:`state_anchor`(第 1 层 `state` 内)是"**读状态、判时机**"的局部(页码框/状态栏/模式标),**不进 procedure**;`anchors`(第 2 层)是"**要操作**"的局部(点/输入),**是 procedure 里 `action` 的对象**。判据:**会不会被 `click/input`**。两者形式都是"局部图 + locator"(同套视觉机制),但职责/所属层不同;game 里两者会重叠(判状态=世界物体本身)→ 并入 `space:世界` 锚点、不另立。

## 4. ★ 完整例子 + 两种形态(看"交错"怎么实现)

### 例 A · GUI「保存对话框:命名并保存」
**存储形态**(三层;Procedure 里**没有图**,只有文字+role+expect):
```
① Context: goal=保存文件; cues=出现保存框[文字+对话框视觉裁剪]; sig=视觉/文字两路嵌入
② Anchors:                                   ← 图都在这里
   filename_field: appearance=[输入框裁剪图]; locator="对话框中部输入框"
   save_button   : appearance=[保存键裁剪图]; locator="右下角主键,在取消键右边"
③ Procedure:                                 ← 只有 文字 + role + expect
   step1: type(filename_field,<text>)    | expect=[框里出现所输入文本的样子]
   step2: click(save_button)             | expect=[对话框消失的样子]
```
**运行形态**(执行时按 `role` 把②的图拉进来 → **每步展开成图文交错**):
```
▶ step1  [文字] 在文件名框输入 "report"
         [图]  filename_field 外观(从②取)  → 对齐:当前屏找到框在哪
         [图]  expect:框里应出现 "report"   → 核验
▶ step2  [文字] 点击保存按钮
         [图]  save_button 外观(从②取)
         [图]  expect:对话框应消失
```
**一句话**:**交错不存在流程里,而是"用的时候"由 role 把②的图现场拼进来**——存得紧凑(图共享、不重复),给 agent 看到的仍是图文交错序列。

### 例 B · Minecraft「砍树」
```
① Context: goal=砍树得木头; cues=前方有树[文字+准星处原木裁剪]; sig=两路嵌入
② Anchors: target_tree(appearance=原木外观; locator="准星正对的最近原木块"; space=世界)
③ Procedure:
   step1: aim_at(target_tree)        | expect=[准星正对该原木块]
   step2: attack(长按) until expect  | expect=[原木裂开消失、木头+1]
```
(注:"选斧子"涉及库存/自身态,按约定先不展开。)

## 5. 适用范围(它管什么 / 不管什么)
- ✅ **吃香**:过程性的"**认状态→定位关键元素→做一段确定步骤**"子任务——**GUI 主体任务 + 过程性游戏**(Minecraft 采集/合成、模拟经营、回合/菜单类)。
- ❌ **排除**:**反应式/实时**(Super Mario、街机、战斗)——静态情境+固定流程撑不住,正是已弃的 dynamic。
- ⚠️ **弱区/可选扩展**:查询/信息型(视觉锚点次要)、条件分支、离屏滚动探索(对齐变搜索)、长程跨 app(需技能组合)——先做核心,这些后扩。

## 6. 与 static / interleaved 的关系(给 paper 用)
- Context+Anchors ≈ **static**(可复用视觉参考);Procedure ≈ **interleaved**(步骤↔证据)。
- **本质 = 升级版 interleaved**:原版 interleaved 每步**内联固定 demo 帧**(看参照);你把证据**抽成可重定位的锚点注册表**、用 `role` 绑定、运行时 materialize → 证据从"静态快照"变成"能在当前屏定位并操作的实体",且图可共享。
- 一句话定位:**不是 static、也不是原版 interleaved,而是"带状态识别(Context)+ 可重定位锚点(Anchors)的 interleaved skill"。**

## 7. ★ 已实现:从纯视频提取多模态 skill(流程 + 成果 · 2026-06-25)
**主张(已验证)**:只给一段操作视频,large VLM **全自主**提取若干三层 skill——**无任务说明、无 action_log、不靠人工标注**。

**提取流程(pipeline v3,脚本落在 `mmskillrl/`)**:
1. **抽帧** `pipe_extract.py`[opencv]:**均匀抽 16 帧**(等时间间隔,resize 1280 宽)。
2. **喂 gpt-5.5**[一次 API]:16 帧 + 帧号 + 提取 prompt(frontier 中转 chat/completions+vision,本机直连)。
3. **VLM 一次吐 JSON**:**按切分准则切 event**(见下;一视频→若干 skill,name 用**英文 snake_case**)+ 每 event 填三层——context(goal/cues 整帧/`cue_frame`=入口帧)、anchors(role/`appearance_frame`/`bbox`/locator,**只操作对象**)、procedure(action/`expect`/`expect_frame`)。
4. **取图** `pipe_extract.py`:按 `appearance_frame`+`bbox`(加 padding)裁锚点**局部**图;按 `cue_frame` 取情境**整帧**。
5. **组织** `pipe_organize.py`:每 event → 一个 skill 文件夹;再 `pipe_paramize.py`(★**纯规则后处理、零 LLM**)把 action 取值 → 占位符。
- **分工**:VLM 看懂 + 指(帧号/bbox/切分),脚本抽帧 + 取图 + 组织 + 规整。

**★ event 切分准则(v7,已验证)**:判据一句——『只看某一帧静态画面,能不能认出该用这个 skill、而不是下一个?』
- **不能区分**(相邻步骤共用同一界面/对话框、且连续必然发生)→ **合并成一个 event**(作为该 skill 的 procedure 多步);
- **能区分**(可独立复用、换 skill 时从画面认得出,如不同页码/菜单/模式)→ 才**拆成多个**。
- 例:插入对话框【点开→选文件→确认】= 一个 skill;【翻页】vs【删页】= 两个。**宁可合并,别切出"一看画面分不出该用哪个"的碎 skill**。

**成果**:`mmskill_example/`(**gui 26**——VideoCUA 的 OnlyOffice/PDFedit **17 个 task** 上量、每个 skill 带 `state` + `state_anchor.jpg`;+ minecraft 5);**`agentnet_skill/`**(**v10 b-full** 产物,LINE 9 终端轨迹 → 4 skill,红点法 anchor + VLM 加工 procedure);记录 `exp_video2skill_2026-06-24.md`。

**检索验证(`retrieval_demo.py`,gpt-5.5)**:query=当前整帧、候选=各 skill 的 goal+锚点局部图,**一次 VLM 调用合 ①检索+②触发+③对齐**。应用切分准则**前 80%(8/10)→后 100%(7/7),零误召回**,锚点对齐中心误差 ≈0.018。证实:原误召回**主因是切分过碎**(三层结构未改即修复)。

**★ 情境 `state`(v8,已验证)**:§2 第 1 层加 `state`(`mode`+`precondition`+`state_anchor`),专补"**判时机**"维度(`cues` 只描述场景、不够判别)。pipeline 升 **v4**:`pipe_extract` 让 VLM 多吐 `state`(看 `cue_frame` 读模式/前置 + 指 state_anchor bbox),`pipe_organize` 带 `state_anchor.jpg`,`retrieval_demo` 改用 **state 判触发**(候选=goal+mode+precondition+state_anchor,**不用操作锚点**)。**验证(上量 26 skill)**:之前"同画面不同模式/前置"的撞车**全修好**——翻页(10)/删页(11)靠 `precondition` 页码(1/9 vs 3/9)分开、批注(18)/字号(19)靠 `mode`+状态栏(InsertTextAnnotation vs InsertText)分开;触发准确率 **~86%**。残留撞车是**切分偏细**(连续链 06-09 被切碎、连 state 都分不开),与 state 无关。

**质检后定的规则(已应用)**:① bbox 加 **padding**;② `cue_frame` 取**入口帧**;③ **anchors 只放操作对象、结果归 `expect`**(§2④);④ **`input/select` 取值参数化**(占位符 `<text>`,§2 关键④);⑤ **event 切分准则**(连续不可分→合并,见上)。

**★ 数据源转向 AgentNet(v9)**:目标 = **以 OSWorld 为基准刷分、对标 MMSkills**(`2605.13527`;benchmark = OSWorld/macOSWorld/VAB-Minecraft/Super Mario,skill 源 = OpenCUA = `xlangai/AgentNet` 的对应 OS 子集)。**VideoCUA 实测是跨 OS 杂数据**(PyCharm/Zotero=macOS Retina、Inkscape/PDFedit=Windows,分辨率 1366~3360 五花八门、无统一 Ubuntu)→ **刷不了 OSWorld**,退为方法论验证(切分准则+state 已在它上面验证有效)。改用 **AgentNet Ubuntu 子集**:`agentnet_ubuntu_5k.jsonl`(5K 轨迹)+ `ubuntu_images`(multi-volume zip,`7z` 解,~70GB)+ `win_mac_18k`;每条 traj = `image` 截图序列 + `value.code`(PyAutoGUI 归一化坐标) + `observation`,**OS 已分好**、对齐 OSWorld 的 GNOME 环境。**已验证**:`pipe_extract_agentnet.py`(纯截图、读 traj 截图、切分+三层+state 全复用)跑通一条 terminal 轨迹 → 4 skill 含 state、确认 GNOME 桌面;文字层(goal/cues/procedure/state)优秀,**视觉锚点 bbox 对小元素裁不准**(见已知待解④)。

**★ 提取方案确立 b-full(v10,已验证)**:a/b 决策(纯截图 vs 用 action 坐标)**定为 b**——依据 65 篇调研(`research_result_video2skill.md`):纯像素反推坐标精度差是公认痛点、主流高质量数据靠底层 log、AgentNet 自带 `value.code` 是最干净信号(真实 OS 事件,比 a11y 还准)。**分工 = VLM 管语义 + 真实 action log 管几何 + VLM 加工**:
- **6 步**:① 读 traj(截图+`value.code`)→ ② VLM 语义(切分+情境层+给 click 起 role 名,不碰流程/坐标)→ ③ 脚本从真实 `value.code` 生成原始 procedure → ④ **VLM 加工**(看 goal:清洗+参数化)→ ⑤ **红点法** anchor → ⑥ 输出。**三次 VLM 调用**:语义/加工/框定;真实 `value.code` 始终存 `raw`,VLM 只生成"模板层",底层可追溯/回退。
- **VLM 加工(解决"真实轨迹噪声+参数化死板")**:① 清洗——打错重打/撤销(`ctrl+u` 清行重输)标 `keep=false` → `dropped_steps` 留档;② 智能参数化——VLM 按 goal 灵活度挖可变槽位、**保留命令骨架**(`touch goast.out`→`touch <file>`、`cd ~/Desktop/pp`→`cd <target_project_folder>`),替代原"规则后处理整体 `<text>`"。
- **红点法(解决原已知待解④小元素 bbox)**:真实 `click_xy` 画红点 → 整帧喂 VLM 框紧 bbox → **四档** `vlm_box`/`fallback_vlm_fail`/`fallback_box_miss`/`fallback_box_toobig`(面积>0.25)。**真实坐标钉中心(不歪)、VLM 只估框大小**,同 SoM/Video2GUI。只 `click` 类有 anchor。
- **健壮性**:`parse_action` 抽样 300 traj `other` 仅 0.69%(补 tripleClick/wait);anchor 严格跟随加工后 procedure 的 click 步(防张冠李戴);frame_range/bbox/JSON 全健壮化、每 event try 续跑。
- **实证(LINE 9 终端)**:锚点框对终端图标(非 LibreOffice)、纠错噪声清掉、`touch <file>`/`cd <target_project_folder>` 参数化对。脚本 `pipe_extract_agentnet.py`(b-full v2),产物 `agentnet_skill/`。

**已知待解**:① Minecraft **世界物体** bbox 框歪 → 需 `space:世界`+相对位置;② 触发"同画面不同模式/前置"撞车 → **已用 §2 `state` 修**(v8);③ 抽帧均匀(长视频需语义选帧);④ **已解决**:原"纯截图小元素 bbox 不准 + a/b 未定"——v10 定 b、用「红点法」(真实坐标钉中心+VLM 框边界)根治,LINE 9 锚点框对终端图标(`vlm_box`);新残留 → **VLM 切分不稳定**(同条 traj 2↔4 波动、偏碎,纯随机性,待治);⑤ `state_anchor` 当"状态=整桌面"时允许 `null`(整帧退化边界)。

**数据源**:**主用 `xlangai/AgentNet` Ubuntu 子集**(对齐 OSWorld;辅 `ubuntu_osworld_verified_trajs`、成品对标 `zhangkangning/mmskills`);旧:VideoCUA(`2603.24440`,跨 OS、退为方法论验证)、GameFactory-Minecraft、VideoAgentTrek(`2510.19488`)。详见 memory `project_mmskillrl_osworld_datasource`。

**下一步**:① **治切分波动**(VLM 切分同条 traj 2↔4、偏碎——prompt 强化"宁可合并" or 后处理合并同界面连续 event);② **上量批量提** AgentNet Ubuntu(b-full,分批 `7z` 解 `ubuntu_images`);③ Minecraft 加 `space`;④ 推进四步「检索/对齐」(`sig` 双路嵌入)。(a/b 已定 b、done)

## 8. 资源 / 暂缓
- 同目录:`research_result_video2skill.md`、`data_sources.md`、`paper_list_video2skill.md`(末尾反面参照 2606.20363)。
- 已有实测(背景,指导选难任务):8B 在 ScreenSpot(易+强模型)上 static 没用反伤、interleaved 视觉=文本 → **技能价值在难任务/弱模型**(故选 GUI 难任务 + Minecraft)。
- 远端 `squirrelai-1-a800`:vLLM 8B(`serve_8b.sh`)、AutoVisualSkill repo `/tmp/AVS`、OSWorld 基建 `/data/hwt/OSWorld`、ScreenSpot `/data/hwt/hf_data`。
- **暂缓**:RL(管理/精炼/内化)、技能进化——当前推进「三层定义 + 四步适配 + §7 视频提取实验」。
