# 实验记录:纯视频 → gpt-5.5 → 三层 skill(v1)

> 时间 **2026-06-24** · 对应 `CLAUDE.md` §7 的视频提取实验

## 0. 目标
验证「只给操作视频,让 large VLM **自主**切 event、提取三层 skill」是否可行(§7 主张:只给视频、无人工标注)。

## 1. 环境(远端 `squirrelai-1-a800` = gpu-a800-060)
- **conda env**: `/data/hwt/envs/videocua`(python 3.11;hf_hub + opencv-python-headless + requests)。conda 在 `/root/miniforge3`(登录为 root)。
- **模型**: gpt-5.5 via frontier 中转(`/v1/chat/completions` + vision 实测可用;见 [[project_claudecode_gpt5_via_litellm]])。
- **数据**: VideoCUA(`ServiceNow/VideoCUA`,走 hf-mirror)→ `/data/hwt/hf_data/videocua_sample`;已下 OnlyOffice Forms + PDFedit(只下小应用 zip,磁盘 /data 仅剩 ~148G)。
- **脚本**: `extract_pure.py`(均匀抽帧 → base64 → gpt-5.5 → 三层 JSON)、`extract_skill.py`(action_log 抽帧版,对照用)、`crop_anchors.py`(按 action_log 坐标裁锚点图)。

## 2. Pipeline
视频 → opencv **均匀抽 N 帧** → 每帧 base64 + 帧号文字 → 喂 gpt-5.5(prompt:切 event + 每 event 填三层,情境/锚点/expect 都用**帧号**引用)→ 输出 `events[]` JSON。"VLM 指帧、程序取帧"。

## 3. 结果
| 样本 | 时长/动作 | 帧 | 切出 event | 备注 |
|---|---|---|---|---|
| 41765 OnlyOffice | 19.6s / 8 | 16 均匀 | 3(开 Forms→插复选框→插下拉) | 高质量 |
| 41768 OnlyOffice | 16.9s / 2 | 16 | 1(应用 form2 样式) | 加了 verify |
| 47588 PDFedit | 31.4s / 7 | 16 | 2(翻页→File-Pages-删页) | 多级菜单 + 页码(3/9→3/8)当验证 |
| 47590 PDFedit | 22.8s / 12 | 16 | 3(Insert→选图→Ok) | 读出文件路径 |
| 47590 PDFedit | 22.8s / 12 | **6** | 3 | event 对,但细节丢(文件名→只能猜) |

### 关键结论
1. **纯视频成立**:无 instruction、无 action_log,gpt-5.5 自主切 event + 提三层,跨 2 应用、短/长/密/多级菜单都稳。三版对比(action_log抽帧+instr / 纯自主 / 真·纯视频均匀帧)结果一致。
2. **VLM 真在自主选帧**:均匀帧池里,它挑的 `appearance_frame` 正好是元素出现的帧(forms_tab@1, checkbox@5, dropdown@13),不是被喂的。
3. **均匀帧"够不够"分层**(减帧 16→6):event 切分 6 帧也对;锚点**细节**(文件名/参数值)随帧数降。→ 切 event 均匀够用,抠细节要密帧或自适应选帧。
4. **action_log = VideoCUA 自带真值**(鼠标动作类型+时间+坐标),野生视频没有;当前仅用于裁锚点图 / 对照,**不是方法依赖**。

## 4. 数据 / 约束
- VideoCUA 视频都短(≤31s),**测不出"长视频(几分钟)均匀帧漏帧"的极限**——要 YouTube 类长视频另测。
- 真·纯视频场景(野生录屏)无 action_log:锚点坐标要么纯靠 VLM,要么逆动力学从画面推(见 VideoAgentTrek)。

## 5. 抽帧 / 切 event 方法调研(备选,按需上)
- **切 event**:CLIP 相邻帧相似度 + KTS(零训练)、SBD 预测误差边界(`2503.10684`)、VLM 直接吐时间戳(TRACE `2410.05643` / LITA `2403.19046`)、VideoAgentTrek(`2510.19488`,GUI 专用需训练)。
- **选关键帧**:AKS(`2502.21271`)、AdaRD-Key(`2510.02778`,相关性+多样性)、Agentic 取帧(AKeyS `2503.16032` / A.I.R. `2510.04428`)。

## 6. 下一步候选
- 锚点图裁剪 → 合成"语义 + 视觉"完整多模态 skill 样本(三层带上真实锚点图)。
- 更长视频(几分钟)测均匀帧极限 + 上自适应选帧(CLIP+KTS / AKS)。
- 批量跑、定义 skill 的存储格式。

## 7. 续(2026-06-25):完整多模态 skill + 自适应选帧
- **完整多模态 skill 落地**:让 gpt-5.5 在每个 anchor 多输出 `bbox`(它自己框,纯视频、不用 action_log),按 bbox 裁锚点图。41765 的 7 个锚点图(forms_tab/checkbox/dropdown/编号项/插入控件)裁出来**全部框对**——VLM 对**有文字标签的标准 UI 控件** bbox 定位相当准(之前 action_log 对照发现的偏差主要在"动作顺序",不在"元素定位")。三层 skill 现在 = 语义 role × **视觉锚点图** × 帧号。脚本 `extract_full.py`,产物 `skill_full.json` + `anchors_full/`。
- **自适应选帧可行**:`extract_adaptive.py` 用 HSV 直方图帧差选"画面变化大"的帧(零依赖,无需 CLIP/torch)。47588(31s)自适应 12 帧 vs 均匀 16 帧 → 切出的 event **一致**(翻页 + 删页),更少帧达同质量。但短视频上自适应与均匀**打平**,优势(省帧 / 不漏窄窗口)要**长视频**才显(VideoCUA 最长 31s,测不到)。
- **小结**:多模态 skill(语义+视觉)在纯视频上**完整跑通**;抽帧策略 均匀/自适应 在短视频上等价。后续:找长视频(YouTube)验证自适应/长极限,或推进 batch / skill 存储格式 / Minecraft。
