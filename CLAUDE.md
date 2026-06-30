# mmskillrl — 工程说明(工作流 & 环境)

> **主线**:`task → trajectory → 多模态 skill`。
> - **task-traj 三条路线**:① GPT 直接生成任务 · ② PEEU(探索→反推) · ③ Video2GUI(视频→轨迹)。
> - **多模态 skill 的「总结方式 / 结构」尚未定**。
> - **后续**:多模态 skill 经 **OPD / OPSD / OPCD** 蒸馏进 agent。
> - 方案/进展细节见 `doc/`。

## 1. 开发工作流:本地 → GitHub → 远程(**不要再 scp**)
- 远程仓库(单一事实源):`https://github.com/wentaohu1208/mmskills`(private,分支 `main`)。
- **流程**:① 本地 `/Users/wentaohu/project/mmskillrl` 改 → ② `commit` + `push`(走代理 `-c http.proxy=127.0.0.1:7897`)→ ③ 远程 `git pull` → ④ 把 `*.py` 同步进运行目录 `/data/hwt/OSWorld`。
- **禁止**直接 scp 改动到远程;一切以 GitHub 为准。

## 2. 远端服务器 / 路径
- **远端主机**:`squirrelai-1-a800`(= gpu-a800-060)。
- **运行地** `/data/hwt/OSWorld` = `xlang-ai/OSWorld` 克隆;脚本依赖 `desktop_env`,**必须在此跑**。
- **mmskills 远程克隆** `/data/hwt/mmskills` = GitHub 拉取落点;`git pull` 后把 `osworld_*.py` 同步进 OSWorld。
- **Conda 环境** `/data/hwt/envs/mmskills`(Python 3.11,含 `gymnasium` / `desktop_env`);跑 explorer / hindsight / run.py 一律用 **`/data/hwt/envs/mmskills/bin/python`**(系统 `python3` 缺依赖)。
- **HF 缓存**:模型 `/data/hwt/hf_ckpt`、数据 `/data/hwt/hf_data`。
- **数据 / 服务**(均在远端 `/data/hwt/OSWorld`):`explore_*`、`peeu_osworld`、`rollout_8b`、`judged_full.jsonl` 等;vLLM 8B 服务 `serve_8b.sh`;ScreenSpot 数据 `/data/hwt/hf_data`。

## 3. GPT-5.5 端点(运行时注入,**不入库**)
- `OPENAI_BASE_URL` / `OPENAI_API_KEY` / `OSWORLD_PROPOSER_MODEL=gpt-5.5` 运行时手动 `export`;**密钥绝不写进任何文件 / 仓库**。
