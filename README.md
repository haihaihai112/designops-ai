# DesignOps AI

面向室内设计场景的本地模型运营工作台。输入一段中文空间需求，系统会完成结构化解析、设计知识检索、候选方案生成、质量评分和版本留存；运营人员可以比较候选图、提交人工反馈、采用或淘汰方案，并在看板中追踪模型质量、兜底率和采用率。

项目拆成独立模块，既可以单独运行 LoRA 数据整理、知识检索或 Agent，也可以通过 Web 工作台走完整的“生成 → 评估 → 反馈 → 复盘”闭环。

## 功能

- 识别常见室内风格和空间类型。
- 将面积、材质、灯光、家具、布局、氛围和配色解析为结构化 Brief。
- 基于本地 ChromaDB 知识库检索风格、材质、灯光和素材管理规范。
- 展示 RAG 来源、相似度和引用片段，结果可随项目报告导出。
- 通过 DeepSeek、Qwen、Ollama 等 OpenAI 兼容接口生成英文绘图提示词和交付说明。
- LLM 不可用时使用本地模板继续生成提示词，便于演示和离线排查。
- 调用 ComfyUI 文生图工作流，并将结果保存到 `outputs/`。
- 生成均衡、创意、落地三类候选，并记录自动质量分和阶段耗时。
- 使用 SQLite 保存项目、候选版本、人工评分、采用/保留/淘汰决策。
- 提供项目历史、方案画廊、Markdown 报告和模型运营看板。
- 提供 LoRA 训练数据整理脚本和隔离外部服务的自动化测试。

## 项目结构

```text
.
├── config.py                   # 模型、知识库和 ComfyUI 配置
├── module1_lora/
│   ├── data_prep.py            # LoRA 训练数据整理
│   └── train_config.toml       # kohya_ss 训练参数示例
├── module2_rag/
│   ├── design_knowledge/       # 设计知识文档
│   ├── build_knowledge_base.py # 构建 ChromaDB 索引
│   └── query_knowledge.py      # 知识库查询接口
├── module3_agent/
│   ├── agent_pipeline.py       # 需求到提示词、brief 的主流程
│   ├── prompt_templates.py     # 提示词模板与风格预设
│   ├── requirement_parser.py   # 结构化需求解析
│   ├── quality_evaluator.py    # 可解释自动质量评分
│   └── comfyui_client.py       # ComfyUI API 客户端
├── module4_demo/app.py         # Gradio 模型运营工作台
├── module5_ops/
│   ├── store.py                # SQLite 项目、版本和反馈存储
│   └── report.py               # Markdown 项目报告导出
├── tests/                      # pytest 自动化测试
└── batch_generate.py           # 批量生成示例场景
```

## 环境准备

建议使用 Python 3.10 或更高版本。图像生成需要本机运行 ComfyUI，并在其中安装 `config.py` 指定的 checkpoint；只运行检索、提示词生成或 Web 界面则不需要 GPU。

```bash
git clone git@github.com:haihaihai112/designops-ai.git
cd designops-ai
python -m venv .venv
```

激活虚拟环境后安装依赖：

```bash
# Windows PowerShell
.\.venv\Scripts\Activate.ps1

pip install -r requirements.txt
```

## 配置

复制示例文件为 `.env`，填写一个 OpenAI 兼容的接口配置：

```bash
Copy-Item .env.example .env
```

```env
LLM_API_BASE=https://api.deepseek.com/v1
LLM_API_KEY=your-api-key
LLM_MODEL=deepseek-chat
```

使用 Ollama 时可将 `LLM_API_BASE` 改为 `http://127.0.0.1:11434/v1`，并配置已下载的模型名。ComfyUI 地址、默认 checkpoint、分辨率和输出目录在 `config.py` 中设置。

## 运行

### 1. 构建设计知识库

首次运行需要下载嵌入模型。完成后索引保存在 `module2_rag/chroma_db/`。

```bash
python module2_rag/build_knowledge_base.py
```

可通过命令行检查检索结果：

```bash
python module2_rag/query_knowledge.py "侘寂风客厅适合什么灯光"
```

### 2. 运行 Agent

```bash
python module3_agent/agent_pipeline.py "设计一个 20 平米的侘寂风客厅，带落地窗和亚麻沙发"
```

如果未配置 LLM，Agent 会提示并使用本地模板；如果 ComfyUI 未运行，则保留提示词和分析结果并跳过图片生成。

### 3. 启动 Web 界面

```bash
python module4_demo/app.py
```

打开 `http://127.0.0.1:7860`。工作台包含三个视图：

- **设计台**：输入需求，生成 1 个或 3 个候选，查看自动评分与知识引用，提交人工评估。
- **项目库**：回看候选版本和历史图片，导出包含 Prompt、质量诊断与引用的 Markdown 报告。
- **运营看板**：查看项目量、候选量、自动质量分、人工评分、采用率和离线兜底率。

首次启动时，如果 `outputs/batch_results.json` 存在，系统会将历史批量生成记录一次性导入看板。运行数据保存在 `data/designops_ops.sqlite3`，该文件默认不提交到 Git。旧版本的 `data/interiorforge_ops.sqlite3` 会在首次启动时自动迁移。

### 4. 整理 LoRA 训练数据

```bash
python module1_lora/data_prep.py \
  --input_dir ./raw_images \
  --output_dir ./training_data \
  --style wabisabi
```

脚本会检查图片、按目标短边缩放、生成 caption 文件，并输出训练数据统计。训练时可参考 `module1_lora/train_config.toml`。

## 输出说明

Agent 返回以下内容：

| 字段 | 说明 |
| --- | --- |
| `positive_prompt` / `negative_prompt` | 适用于 Stable Diffusion 的英文正反向提示词 |
| `params` | CFG、采样步数和采样器 |
| `analysis` | 中文设计思路摘要 |
| `coohom_brief` | 可用于建模、材质和灯光配置的英文 brief |
| `asset_tags` | 场景和素材的分类、风格、材质与检索标签 |
| `social_copy` | 可继续编辑的标题、正文、标签和短视频脚本 |
| `image` | ComfyUI 生成结果或失败原因 |
| `structured_requirement` | 风格、空间、面积和分类约束 |
| `rag_citations` | 知识来源、引用片段和向量距离 |
| `quality` | 需求覆盖、意图一致、交付完整和 Prompt 质量分 |
| `timings` | 解析、检索、LLM、出图和总耗时 |
| `generation_mode` | `llm`、`fallback` 或历史数据 `legacy` |

## 测试

自动化测试不会调用真实 LLM、Embedding 服务或 ComfyUI：

```bash
pytest
```

测试覆盖结构化需求、双语关键词评分、Agent 离线兜底合同、候选版本、人工反馈、看板指标、历史数据幂等导入和报告导出。

## 常见配置

| 部分 | 默认实现 | 可替换项 |
| --- | --- | --- |
| LLM | DeepSeek OpenAI 兼容接口 | Qwen、Ollama 或其他兼容接口 |
| Embedding | `BAAI/bge-small-zh-v1.5` | 任意 sentence-transformers 模型 |
| 向量库 | ChromaDB | 保持查询接口后可替换 |
| 图像生成 | ComfyUI + SD 1.5 工作流 | 自定义 ComfyUI 工作流或 checkpoint |

## 注意事项

- `.env`、生成图片、向量库和模型文件默认不会提交到仓库。
- `data/` 中的 SQLite 运行数据默认不会提交，可删除数据库以重置工作台状态。
- 知识文档更新后，需要重新运行构建脚本以刷新索引。
- ComfyUI 中的 checkpoint 文件名必须与 `config.py` 的 `SD_DEFAULTS["checkpoint"]` 一致。

## License

MIT
