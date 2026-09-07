<div align="center">

# InteriorForge AI

**面向室内设计团队的模型运营工作台**

[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=flat&logo=python&logoColor=white)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green?style=flat)](https://opensource.org/license/mit/)
[![Tests](https://img.shields.io/badge/tests-pytest-0A9EDC?style=flat&logo=pytest&logoColor=white)](tests/)
[![GitHub](https://img.shields.io/badge/GitHub-haihaihai112%2Fdesignops--ai-181717?style=flat&logo=github)](https://github.com/haihaihai112/designops-ai)

</div>

InteriorForge AI 把一段中文空间需求转换成结构化 Brief、设计知识引用、英文绘图 Prompt 和候选方案。它还会记录自动评分、人工反馈和版本结果，方便比较方案并复盘模型表现。

项目适合做两件事：

- 用本地模板或 OpenAI 兼容接口生成设计交付物。
- 用 ComfyUI 或 OpenAI Images API 出图，再把结果放回同一条评估和运营链路。

## 运行流程

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
ComfyUI / OpenAI Images API
    |
SQLite 版本、反馈和运营指标
```

RAG 查询使用语义距离、关键词重合和 MMR 多样性重排。生成后的 Prompt 会检查材质、家具和灯光等硬约束，必要时补充英文别名。图像 provider 支持 `comfyui`、`openai` 和 `auto`。

## 运行预览

示例输出来自仓库内的批量生成结果：

| 方案样张 | 方案样张 | 方案样张 |
| --- | --- | --- |
| ![室内方案 1](outputs/interior_design_00004_.png) | ![室内方案 2](outputs/interior_design_00008_.png) | ![室内方案 3](outputs/interior_design_00010_.png) |

## 快速开始

### 1. 安装

需要 Python 3.10 或更高版本。

```bash
git clone https://github.com/haihaihai112/designops-ai.git
cd designops-ai
python -m venv .venv
```

Windows PowerShell：

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

### 2. 配置文本模型

项目使用 OpenAI 兼容接口生成 Prompt。可以接入 DeepSeek、Qwen、Ollama 或其他兼容服务。

```env
LLM_API_BASE=https://api.deepseek.com/v1
LLM_API_KEY=your-api-key
LLM_MODEL=deepseek-chat
```

没有可用的 LLM 时，Agent 会使用本地模板继续生成结果。API Key 只放在 `.env` 或系统环境变量中，不要提交到仓库。

### 3. 构建设计知识库

知识文档位于 `module2_rag/design_knowledge/`。首次构建会加载本地 Embedding 模型并生成 ChromaDB 索引。

```bash
python module2_rag/build_knowledge_base.py
python module2_rag/query_knowledge.py "侘寂风客厅适合什么灯光"
```

### 4. 运行 Agent

```bash
python module3_agent/agent_pipeline.py "设计一个 20 平米的侘寂风客厅，带落地窗和亚麻沙发"
```

不启动 ComfyUI 时，可以只生成 Prompt 和评估结果：

```python
from module3_agent.agent_pipeline import run_agent

result = run_agent(
    "20平米侘寂风客厅，亚麻沙发、原木茶几、落地窗、暖光",
    generate=False,
    variant="practical",
)
print(result["positive_prompt"])
print(result["quality"])
```

### 5. 启动工作台

```bash
python module4_demo/app.py
```

浏览器打开 <http://127.0.0.1:7860>。工作台包含三个视图：

- 设计台：输入需求，生成一个或三个候选方案，查看 Prompt、评分和知识引用。
- 项目库：查看历史版本、图片和 Markdown 报告。
- 运营看板：查看项目量、候选量、自动质量分、人工评分、采用率和离线兜底率。

## 图像生成

### ComfyUI

本地 ComfyUI 适合需要自定义 checkpoint、LoRA、ControlNet 或工作流的场景。地址、checkpoint、分辨率和输出目录在 `config.py` 中配置。

```env
IMAGE_PROVIDER=comfyui
```

### OpenAI Images API

OpenAI API 适合没有本地 GPU 或需要快速验证云端链路的场景。图片保存到 `outputs/api/`。

```env
IMAGE_PROVIDER=openai
OPENAI_API_KEY=your-openai-api-key
OPENAI_IMAGE_MODEL=gpt-image-1
OPENAI_IMAGE_SIZE=1024x1024
OPENAI_IMAGE_QUALITY=auto
```

代码中也可以显式指定 provider：

```python
result = run_agent(
    "20平米侘寂风客厅，亚麻沙发和落地窗",
    generate=True,
    image_provider="openai",
)
print(result["image"])
```

### 自动选择

```env
IMAGE_PROVIDER=auto
```

`auto` 先检查 ComfyUI。ComfyUI 不可用且配置了 `OPENAI_API_KEY` 时，Agent 会切换到 OpenAI Images API；两者都不可用时保留文本结果并返回失败原因。

OpenAI 官方接口说明：<https://developers.openai.com/api/docs/guides/images-vision>

## 项目结构

```text
.
├── config.py                       # LLM、Embedding、ComfyUI 和图像 API 配置
├── module1_lora/
│   ├── data_prep.py                # LoRA 训练数据整理
│   └── train_config.toml            # 训练参数示例
├── module2_rag/
│   ├── design_knowledge/            # 室内设计知识文档
│   ├── build_knowledge_base.py      # 构建 ChromaDB 索引
│   └── query_knowledge.py           # 查询与 MMR 重排
├── module3_agent/
│   ├── agent_pipeline.py            # Agent 主流程
│   ├── requirement_parser.py        # 需求解析
│   ├── quality_evaluator.py         # 解释型质量评分
│   ├── comfyui_client.py            # ComfyUI 客户端
│   └── openai_image_client.py       # OpenAI Images API 客户端
├── module4_demo/app.py              # Gradio 工作台
├── module5_ops/
│   ├── store.py                     # SQLite 项目和反馈存储
│   └── report.py                    # Markdown 报告导出
├── tests/                           # 自动化测试
├── UPGRADE_ROADMAP.md               # 后续升级路线
└── batch_generate.py                # 批量生成示例
```

## 返回结果

`run_agent()` 返回一个字典，常用字段如下：

| 字段 | 内容 |
| --- | --- |
| `structured_requirement` | 风格、空间、面积和分类约束 |
| `positive_prompt` / `negative_prompt` | 英文正向和反向提示词 |
| `params` | CFG、Steps 和采样器 |
| `rag_citations` | 来源、引用片段和距离 |
| `prompt_repair` | 被补回的约束项 |
| `quality` | 需求覆盖、意图一致、交付完整和 Prompt 质量 |
| `image` | provider、图片路径、成功状态和错误信息 |
| `timings` | 解析、检索、LLM、出图和总耗时 |
| `generation_mode` | `llm`、`fallback` 或 `legacy` |

## 测试

测试不调用真实 LLM、Embedding 服务、ComfyUI 或 OpenAI Images API：

```bash
pytest -q
python -m compileall -q module2_rag module3_agent module4_demo module5_ops
```

当前测试覆盖需求解析、双语关键词评分、RAG 重排、Prompt 修复、Agent 离线兜底、API Key 缺失处理、候选版本、人工反馈、看板指标、历史数据导入和报告导出。

## 后续路线

升级计划和交接模板见 [UPGRADE_ROADMAP.md](UPGRADE_ROADMAP.md)。当前优先级是：

1. 增加 provider 重试、请求追踪、耗时和成本指标。
2. 将检索升级为 Dense Embedding、BM25 和 Cross-Encoder 的混合召回。
3. 接入 CLIP 或 DINOv2 做图文一致性和图像质量评估。
4. 用人工采用、保留和淘汰记录训练候选排序器。
5. 在 ComfyUI 路线增加 ControlNet、IP-Adapter 和多视角一致性约束。

## 相关文档

- [升级路线](UPGRADE_ROADMAP.md)
- [OpenAI Images API](https://developers.openai.com/api/docs/guides/images-vision)
- [ComfyUI](https://github.com/comfyanonymous/ComfyUI)
- [MIT License](https://opensource.org/license/mit/)

## License

MIT
