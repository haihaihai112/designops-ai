<div align="center">

# InteriorForge AI

**面向室内设计团队的 AI 方案生成与模型运营工作台**

[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=flat&logo=python&logoColor=white)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green?style=flat)](https://opensource.org/license/mit/)
[![Tests](https://img.shields.io/badge/tests-pytest-0A9ED9?style=flat&logo=pytest&logoColor=white)](tests/)
[![GitHub](https://img.shields.io/badge/GitHub-haihaihai112%2Fdesignops--ai-181717?style=flat&logo=github)](https://github.com/haihaihai112/designops-ai)

</div>

InteriorForge AI 接收中文室内设计需求，生成结构化 Brief、知识引用、英文绘图 Prompt 和一至三个候选方案。团队可以比较候选、锁定设计约束、提交反馈、继续迭代，并查看任务状态、质量评分和成本估算。

项目默认通过 OpenAI Images API 生图。ComfyUI 不出现在 Web 界面中，仅保留一个默认关闭的私有化适配器。文本生成支持 OpenAI 兼容接口和 LiteLLM；未配置可用模型或外部服务时，文本链路会切换到本地模板，但不会生成真实图片。

## 主要功能

- 将风格、空间、面积、材质、灯光、家具、布局和氛围解析为结构化需求。
- 从本地设计知识库检索依据，并使用语义距离、关键词重合和 MMR 完成重排。
- 生成一至三个候选方案，自动修复 Prompt 中遗漏的约束，并保存质量评分与知识引用。
- 支持候选采用、迭代和淘汰。迭代版本会记录父候选、修改要求和继承的锁定约束。
- 使用 SQLite 保存项目、候选、反馈和任务；生产模式可通过 Redis 与 RQ 执行可重试任务。
- 提供任务进度、取消、幂等键、单任务预算和月度预算检查。
- 可选接入视觉模型评测生成结果，并通过 Phoenix 记录链路追踪。
- 提供固定离线评测集、Markdown 项目报告和 GitHub Actions 持续集成。

## 系统流程

```text
中文需求
    |
结构化解析（风格、空间、面积、材质、灯光、家具、布局、氛围）
    |
本地 RAG 检索（ChromaDB + sentence-transformers）
    |
LLM 生成 Prompt 和交付物
    |                    \
    |                     +-- 本地模板兜底
    |
Prompt 约束修复 + 质量评分
    |
OpenAI Images API
    |
视觉模型结果评测（可选）
    |
SQLite 版本、异步任务、反馈和运营指标

横向能力：Redis/RQ 可恢复队列 | LiteLLM 模型路由 | Phoenix Trace | smolagents 工具调用
```

知识库不存在时，系统会在首次查询时构建索引。设置 `AUTO_BUILD_KNOWLEDGE_BASE=0` 可以关闭自动构建。Web 工作台通过持久化任务执行候选生成，允许用户锁定空间、风格、面积、布局、材质、家具和灯光约束。

## 快速开始

### 独立 Web 工作台

先安装 Python 依赖并准备 `.env`，然后分别启动 API 与前端：

```bash
uvicorn module7_api.app:app --reload --port 8000
cd frontend
npm install
npm run dev
```

工作台位于 <http://localhost:3000>，API 文档位于 <http://localhost:8000/docs>。

### Windows 兼容界面

在项目根目录打开 PowerShell：

```powershell
.\install.ps1
python setup_env.py
.\start.ps1
```

安装脚本会创建 `.venv`、安装完整依赖并准备 `.env`。配置向导会询问文本模型、OpenAI 图片服务、可选视觉评测模型和端口。没有 API Key 时可以直接回车，使用本地模板完成文本处理。

### Linux 或 macOS 兼容界面

```bash
chmod +x install.sh start.sh
./install.sh
python setup_env.py
./start.sh
```

Gradio 兼容界面位于 <http://127.0.0.1:7860>。

### Docker

需要 Docker 和 Docker Compose：

```bash
cp .env.example .env
docker compose up -d --build
```

工作台位于 <http://localhost:3000>，Gradio 兼容界面位于 <http://127.0.0.1:7860>。Docker Compose 会启动 API、Web、Redis 和独立 RQ Worker。生成结果、SQLite 数据、Redis 队列和 ChromaDB 会保存在持久卷或宿主机目录中。

## 配置

配置项可以写入 `.env`，也可以运行 `python setup_env.py` 生成配置文件。API Key 只应保存在 `.env` 或系统环境变量中，不应提交到仓库。

### 文本模型

项目使用 OpenAI 兼容接口，可以接入 DeepSeek、Qwen、Ollama 或其他兼容服务：

```env
LLM_API_BASE=https://api.deepseek.com/v1
LLM_API_KEY=your-api-key
LLM_MODEL=deepseek-chat
```

Ollama 示例：

```env
LLM_API_BASE=http://localhost:11434/v1
LLM_API_KEY=ollama
LLM_MODEL=qwen2.5:7b
```

需要统一模型入口时，可以启用 LiteLLM：

```env
LLM_BACKEND=litellm
LLM_API_BASE=https://api.deepseek.com/v1
LLM_API_KEY=your-api-key
LLM_MODEL=deepseek-chat
LITELLM_MODEL=deepseek/deepseek-chat
```

`LITELLM_MODEL` 需要包含 provider 前缀。模型调用统一经过 `module3_agent/model_gateway.py`，业务管线不依赖具体 SDK。

### 图像生成与评测

默认图像服务是 OpenAI Images API，不需要本地 GPU：

```env
IMAGE_PROVIDER=openai
OPENAI_API_KEY=your-openai-api-key
OPENAI_IMAGE_MODEL=gpt-image-1
OPENAI_IMAGE_SIZE=1024x1024
OPENAI_IMAGE_QUALITY=auto
IMAGE_ESTIMATED_COST_USD=0
```

`IMAGE_ESTIMATED_COST_USD` 是内部估算单价，用于任务预检和运营面板，不代表供应商账单。应按实际模型、尺寸和质量填写。

视觉评测默认关闭。使用可处理图片的多模态模型时，可以配置：

```env
VISION_API_BASE=https://api.openai.com/v1
VISION_API_KEY=your-openai-api-key
VISION_MODEL=your-vision-capable-model
VISION_IMAGE_DETAIL=low
```

系统通过 Responses API 将生成图片作为 `input_image`，评估需求匹配、空间一致性、材质还原和灯光质量。`VISION_MODEL` 留空时跳过该步骤，不影响生成流程。

ComfyUI 适配器默认关闭。私有化部署需要它时，设置 `ENABLE_COMFYUI_ADAPTER=1` 并配置 `COMFYUI_API_BASE`。该选项不会显示在 Web 工作台中。

### 任务队列与预算

本机开发默认使用持久化 `inline` 模式，任务状态保存在 SQLite。API 重启后会恢复未完成任务。Docker 和生产部署可以使用 Redis 与 RQ：

```env
TASK_QUEUE_BACKEND=rq
REDIS_URL=redis://redis:6379/0
TASK_QUEUE_NAME=interiorforge
TASK_TIMEOUT_SECONDS=600
TASK_MAX_RETRIES=2
```

生成接口支持 `Idempotency-Key`，相同键不会重复创建任务。任务可以查询进度和请求取消。系统在任务入队前按单图估算价格检查预算：

```env
IMAGE_ESTIMATED_COST_USD=0.04
MAX_JOB_COST_USD=0.15
MONTHLY_IMAGE_BUDGET_USD=20
```

预算值为 `0` 时不限制。图片 API 返回的 `usage` 会随候选结果保存，可用于后续接入实际计费规则。

### Phoenix 可观测性

启动本地 Phoenix：

```bash
docker compose --profile observability up -d phoenix
```

然后启用追踪：

```env
PHOENIX_ENABLED=1
PHOENIX_PROJECT_NAME=interiorforge-ai
PHOENIX_COLLECTOR_ENDPOINT=http://localhost:6006/v1/traces
```

Phoenix 页面位于 <http://localhost:6006>。系统记录主管线、需求解析、知识检索、模型生成、质量评估和图像生成 Span；OpenAI 与 LiteLLM 调用由 OpenInference 自动埋点。追踪初始化失败时，业务继续运行，并通过 `observability.warning` 返回原因。

### 服务访问

本机访问可以保留默认值。部署到服务器时可以设置：

```env
GRADIO_SERVER_NAME=0.0.0.0
GRADIO_SERVER_PORT=7860
```

服务暴露到公网时，应同时设置 `GRADIO_AUTH_USER` 和 `GRADIO_AUTH_PASSWORD`，并在反向代理层配置 HTTPS。

## 户型图生图

Gradio 兼容界面的“户型图生图”页可以上传 Pillow 支持的图片。用户填写风格、材质、空间要求和视角后，系统会调用 OpenAI Images 图像编辑接口：

```env
OPENAI_API_KEY=your-openai-api-key
IMAGE_PROVIDER=openai
```

系统先检索本地知识库，再把风格、材质、灯光和家具参考写入图像编辑提示词。户型图中的外轮廓、墙体、门窗、房间相邻关系、湿区和动线具有更高优先级，检索内容不能覆盖这些结构约束。输出用于概念方案展示，不能替代施工图或精确尺寸校核。

## 工具调用 Agent

工具 Agent 提供只读的需求解析、知识检索和 Prompt 评估，不会自动触发付费图像生成：

```bash
python -m module3_agent.tool_agent "设计一个20平米的侘寂风客厅，带落地窗和亚麻沙发"
```

该入口使用 `smolagents.ToolCallingAgent` 和 LiteLLM，因此需要配置 `LITELLM_MODEL` 及对应的 API Key。固定步骤和结构化输出仍使用 `run_agent()`；需要模型自主选择工具时再使用此入口。

## 命令行用法

只生成 Prompt 和评估结果：

```bash
python module3_agent/agent_pipeline.py "设计一个 20 平米的侘寂风客厅，带落地窗和亚麻沙发"
```

查询设计知识：

```bash
python module2_rag/query_knowledge.py "侘寂风客厅适合什么灯光"
```

批量生成示例：

```bash
python batch_generate.py
```

运行固定离线评测集，不调用图片 API：

```bash
python -m module5_ops.evaluation
```

评测报告写入 `outputs/evaluations/`，同时生成 JSON 和 Markdown。报告包括结构化抽取覆盖、最终 Prompt 覆盖、解析准确率、质量分、延迟和兜底率。CI 使用 `--min-parse-accuracy` 与 `--min-constraint-coverage` 设置回归门槛。Web 工作台也可以下载单个项目的 Markdown 版本报告。

## 项目结构

```text
.
├── config.py                       # LLM、Embedding、服务和图像 API 配置
├── setup_env.py                    # 交互式配置向导
├── install.ps1 / install.sh        # 一键安装脚本
├── start.ps1 / start.sh            # 一键启动脚本
├── Dockerfile                      # Docker 镜像
├── docker-compose.yml              # Docker Compose 配置
├── .github/workflows/ci.yml        # 后端、前端和 Compose 持续集成
├── evals/                          # 固定离线评测集
├── module1_lora/                   # LoRA 训练数据整理
├── module2_rag/                   # 设计知识库和检索
├── module3_agent/                 # Agent 主流程、评估和出图客户端
├── module4_demo/                  # Gradio 工作台
├── module5_ops/                   # SQLite 存储、评测和报告导出
├── module6_observability/         # Phoenix/OpenTelemetry 可选追踪
├── module7_api/                   # FastAPI 服务和稳定 HTTP 合约
├── frontend/                      # Next.js 生产工作台
├── tests/                         # 自动化测试
├── requirements-aiops.txt         # LiteLLM、smolagents 和 Phoenix
└── batch_generate.py              # 批量生成示例
```

## `run_agent()` 返回字段

| 字段 | 内容 |
| --- | --- |
| `structured_requirement` | 风格、空间、面积和分类约束 |
| `positive_prompt` / `negative_prompt` | 英文正向和反向提示词 |
| `params` | CFG、Steps 和采样器 |
| `rag_citations` | 来源、引用片段和距离 |
| `prompt_repair` | 被补回的约束项 |
| `quality` | 需求覆盖、意图一致、交付完整和 Prompt 质量 |
| `visual_quality` | 图片需求匹配、空间一致、材质和灯光评测；未配置时返回跳过状态 |
| `decision_score` | 综合 Prompt 质量和图片质量的候选决策分 |
| `image` | provider、图片路径、成功状态和错误信息 |
| `costs` | 按配置单价计算的图片成本估算 |
| `timings` | 解析、检索、LLM、出图和总耗时 |
| `generation_mode` | `llm`、`fallback` 或 `legacy` |
| `llm_backend` | `openai` 或 `litellm` |
| `observability` | Phoenix 是否启用、是否成功连接及初始化警告 |

## 测试

测试不会调用真实 LLM、Embedding 服务、ComfyUI、视觉模型或 OpenAI Images API：

```bash
pytest -q
python -m compileall -q module2_rag module3_agent module4_demo module5_ops module6_observability module7_api
cd frontend && npm run build
docker compose config --quiet
```

GitHub Actions 在提交和拉取请求时执行后端测试、前端生产构建、离线评测与 Compose 配置检查。

## 相关链接

- [OpenAI Image generation](https://developers.openai.com/api/docs/guides/image-generation)
- [OpenAI Images and vision](https://developers.openai.com/api/docs/guides/images-vision)
- [ComfyUI](https://github.com/comfyanonymous/ComfyUI)
- [MIT License](https://opensource.org/license/mit/)

## License

MIT
