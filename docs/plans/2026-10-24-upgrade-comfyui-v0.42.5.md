---
title: Upgrade ComfyUI local tree to upstream v0.42.5
artifact_contract: ce-unified-plan/v1
product_contract_source: ce-plan
execution: code
date: 2026-10-24
---

# Upgrade ComfyUI to upstream v0.42.5

Agent / 日常操作手册见 Gitea [`wilber/ComfyUI_user`](http://192.168.1.84:18600/wilber/ComfyUI_user)（`git@joy-x:wilber/ComfyUI_user.git`），源码仓内摘要见 [`docs/ops/README.md`](../ops/README.md)。

## Goal Capsule

- **Objective:** 本地 ComfyUI 工作区与官方上游 **v0.42.5** 对齐；现有 CPU Docker 部署方式仍可用，并能启动 UI、跑通一条基础工作流。
- **Means:** 因本地相对 `v0.42.5` 无独有业务提交，采用 **hard reset 到 `v0.42.5`**，保留未跟踪的 Docker 文件并按新依赖适配重建镜像。
- **Authority:** 上游 `Comfy-Org/ComfyUI` tag `v0.42.5` > 本计划 > 本地未提交 Docker 定制。
- **Stop conditions:** 升级后版本号非 `0.42.5`；容器无法启动；`requirements` 与 Dockerfile 冲突未解决；用户未授权时执行 `push --force`。
- **Ship owner:** 实现由本机 Agent/操作者完成；推送 fork（`origin`）仅在用户明示后执行。

## Product Contract

### Requirements

- **R1.** 代码树版本等于上游 tag **v0.42.5**（`pyproject.toml` / `comfyui_version.py` 为 `0.42.5`）。
- **R2.** 未跟踪的 `Dockerfile`、`docker-compose.yml`、`.dockerignore` 在升级后仍在工作区，且能按新 `requirements.txt` 构建。
- **R3.** 容器可监听 `8188`，Web UI 可打开。
- **R4.** 至少一条官方/内置简单工作流可排队执行完成（CPU 模式允许慢）。
- **R5.** 不擅自 force-push `origin/master`；不破坏其它正在运行的 Docker 容器。
- **R6.** 升级前可回退：保留 `306af3a8`（当前 `v0.28.2`）引用（本地 tag 或记下 SHA）。

### Out of scope

- 合并到 `upstream/master` tip（可晚于本计划作为可选跟进）。
- 定制 GPU 镜像、模型下载、自定义节点生态全面回归。
- 改写/提交 `.cursor/` 钩子状态。
- 自动同步过时的 `origin/master`（除非用户另下指令）。

### Acceptance examples

- `git describe --tags --exact-match` → `v0.42.5`。
- `docker compose up -d --build` 后 `curl -sS http://127.0.0.1:8188/` 返回 UI/HTML。
- 在 UI 中跑一张最小图生成/空跑类工作流，队列完成无崩溃。

## Planning Contract

### Key technical decisions

- **KTD1 — 对齐方式：`git reset --hard v0.42.5`。**  
  证据：相对 `v0.42.5` 仅 8 个“本地独有” commit；其中 6 个 PR（#14957/#14958/#14972/#14973/#14984/#14986）上游已有等价提交（不同 SHA）；其余为过时版本号 bump。merge 会留下无意义的分叉历史；reset 更干净。  
  备选（不采用除非用户要求）：`git merge v0.42.5` 保留分叉。

- **KTD2 — 目标钉 tag，不钉 `upstream/master`。**  
  `v0.42.5`（2026-10-23）是最新正式 tag；`upstream/master` 仅再超前约 19 commits（文档/杂项）。先稳住可复现版本。

- **KTD3 — Docker 继续 CPU + bind mount。**  
  现有 compose 将仓库挂到 `/app`；镜像需能安装新依赖。`requirements.txt` 相对本地已去掉 `torchaudio`，并升 `comfyui-frontend-package`、`comfy-kitchen`、`comfy-aimdo`、`av` 等——Dockerfile 的 grep 排除逻辑需同步（不再排除已不存在的 `torchaudio` 亦可，但应核对）。

- **KTD4 — `origin` 暂不自动更新。**  
  fork `origin/master` 停在 `535c16ce`，落后本地 721。升级后若要更新 fork，需用户明示（建议新分支或 `push --force-with-lease`）。

### Assumptions

- 上游 `upstream` remote 已可 `fetch`（已验证可拉到 `v0.42.5`）。
- 本机有 Docker；ComfyUI 允许 `--cpu` 运行验收。
- 用户接受丢弃那 8 个等价/过时本地 commit 的 SHA（内容不丢）。

### Sequencing

1. 备份引用 → 2. reset 到 tag → 3. 适配 Docker → 4. 重建冒烟 → 5.（可选）推送 fork。

## Implementation Units

### U1. 备份与对齐代码树

- **Do:**
  - `git fetch upstream --tags`
  - `git tag pre-upgrade-v0.28.2 306af3a8`（若 tag 已存在则跳过）
  - 确认未跟踪 Docker 三件套仍在：`Dockerfile`、`docker-compose.yml`、`.dockerignore`
  - `git reset --hard v0.42.5`
  - 确认 `git status`：工作树干净于上游文件；Docker 三件套仍为 `??`
- **Verify:** `git describe --tags --exact-match` = `v0.42.5`；`cat comfyui_version.py` 含 `0.42.5`。
- **Risk:** reset 会丢掉未提交的已跟踪文件改动——执行前确认无此类改动（当前仅有未跟踪文件）。

### U2. 适配 Dockerfile / compose

- **Do:**
  - 对照新 `requirements.txt` 更新 `Dockerfile`：
    - 保持 CPU torch 预装策略（若仍需要减小体积）
    - 排除列表与现依赖一致（`torch`/`torchvision`；无 `torchaudio` 则不必再 grep）
    - 系统包保留 `libgl1`/`ffmpeg` 等既有项
  - `docker-compose.yml`：继续 `8188:8188`、bind mount `.:/app`、`CLI_ARGS`；确认未与其它项目抢端口（本机 PlantVR 用 8189，ComfyUI 用 8188 可接受）
  - `.dockerignore`：避免把巨大模型/输出目录打进 build context（按现状保留并必要时补 `models/`、`output/`、`.git`）
- **Verify:** `docker compose build` 成功。
- **Risk:** slim 镜像缺系统库导致某节点 import 失败——冒烟阶段记日志，按需补 apt 包，不做大范围预装。

### U3. 重建容器并冒烟

- **Do:**
  - `docker compose up -d --build`（仅本项目 compose，不 prune 影响其它容器）
  - 查容器日志无立即崩溃
  - HTTP 探活 `8188`
  - 在 UI 加载默认/模板工作流并执行一次（CPU）
- **Verify:** R3、R4。
- **Stop:** 持续 OOM / 依赖冲突无法启动 → 回退 `git reset --hard pre-upgrade-v0.28.2` 并报告阻塞依赖。

### U4.（可选，需用户明示）更新 fork

- **Do:** 用户确认后二选一：
  - A. `git push origin HEAD:master --force-with-lease`
  - B. `git push -u origin HEAD:upgrade/v0.42.5` 开 PR 到自己的 fork/用途分支
- **Verify:** `origin` 上目标引用指向 `v0.42.5`。

## Verification Contract

| 检查   | 命令/方式                                                                   |
| ------ | --------------------------------------------------------------------------- |
| 版本   | `git describe --tags --exact-match`；读 `comfyui_version.py`                |
| 工作树 | `git status -sb`：跟踪文件干净；Docker 文件仍在                             |
| 构建   | `docker compose build`                                                      |
| 运行   | `docker compose up -d`；日志无 traceback 循环                               |
| HTTP   | `curl -sS -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8188/` 期望 200 |
| 功能   | UI 队列完成一条最小工作流                                                   |
| 安全   | 未对无关容器 `rm`/`down -v`；未未经授权 force-push                          |

## Definition of Done

- [ ] HEAD == `v0.42.5`
- [ ] 回退 tag `pre-upgrade-v0.28.2` 存在
- [ ] Docker 三件套保留且能 build/up
- [ ] `8188` 可访问；一条工作流跑通
- [ ] 未擅自推送 `origin`；未影响其它 Docker 容器

## Appendix

### 调研快照（2026-10-24）

| 项                    | 值                                                        |
| --------------------- | --------------------------------------------------------- |
| 本地 HEAD             | `306af3a8` · `v0.28.2`                                    |
| 上游目标              | `483dae43` · `v0.42.5`                                    |
| merge-base            | `700821e1` · `v0.28.0`                                    |
| behind / ahead vs tag | 604 / 8（ahead 实质可弃）                                 |
| 文件 diff 规模        | ~751 files，+190k / −22k                                  |
| 正式 Release 页最新   | `v0.42.1`（tag 已到 `v0.42.5`）                           |
| remotes               | `origin`=`1980-X/ComfyUI`；`upstream`=`Comfy-Org/ComfyUI` |
| origin/master         | `535c16ce`（严重过时）                                    |

### 主要依赖跳变（requirements）

- `comfyui-frontend-package` 1.45.21 → 1.55.18
- `comfyui-workflow-templates` 0.11.12 → 0.11.96
- `comfyui-embedded-docs` 0.5.8 → 0.5.14
- `comfy-kitchen` 0.2.20 → 0.2.39
- `comfy-aimdo` 0.4.10 → 0.5.6
- `av` ≥16 → ≥17；移除 `torchaudio` 行

### 建议不采用的路径

- 逐版本 hop（0.29…0.42）：成本高、无独有补丁需要保留。
- 先改业务代码再升级：当前无业务分叉。
- 宿主机 pip 安装跑服务：违反「开源项目必须容器化」偏好。
