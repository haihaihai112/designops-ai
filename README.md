# InteriorForge AI

面向室内设计场景的本地 AI 工作流示例。输入一段中文空间需求，系统会检索设计知识库，生成 Stable Diffusion 提示词、设计说明、Coohom 执行 brief、素材标签和发布文案；在 ComfyUI 可用时还可以直接出图。

项目拆成独立模块，既可以单独运行数据整理或知识检索，也可以通过 Agent 和 Web 界面走完整流程。

## 功能

- 识别常见室内风格和空间类型。
- 基于本地 ChromaDB 知识库检索风格、材质、灯光和素材管理规范。
- 通过 DeepSeek、Qwen、Ollama 等 OpenAI 兼容接口生成英文绘图提示词和交付说明。
- LLM 不可用时使用本地模板继续生成提示词，便于演示和离线排查。
- 调用 ComfyUI 文生图工作流，并将结果保存到 `outputs/`。
- 提供 LoRA 训练数据整理脚本和 Gradio 演示界面。

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
│   └── comfyui_client.py       # ComfyUI API 客户端
├── module4_demo/app.py         # Gradio 界面
└── batch_generate.py           # 批量生成示例场景
```

## 环境准备

建议使用 Python 3.10 或更高版本。图像生成需要本机运行 ComfyUI，并在其中安装 `config.py` 指定的 checkpoint；只运行检索、提示词生成或 Web 界面则不需要 GPU。

```bash
git clone git@github.com:haihaihai112/interior-design-ai-agent.git
cd interior-design-ai-agent
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

打开 `http://127.0.0.1:7860`，输入空间需求即可查看生成结果。

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

## 常见配置

| 部分 | 默认实现 | 可替换项 |
| --- | --- | --- |
| LLM | DeepSeek OpenAI 兼容接口 | Qwen、Ollama 或其他兼容接口 |
| Embedding | `BAAI/bge-small-zh-v1.5` | 任意 sentence-transformers 模型 |
| 向量库 | ChromaDB | 保持查询接口后可替换 |
| 图像生成 | ComfyUI + SD 1.5 工作流 | 自定义 ComfyUI 工作流或 checkpoint |

## 注意事项

- `.env`、生成图片、向量库和模型文件默认不会提交到仓库。
- 知识文档更新后，需要重新运行构建脚本以刷新索引。
- ComfyUI 中的 checkpoint 文件名必须与 `config.py` 的 `SD_DEFAULTS["checkpoint"]` 一致。

## License

MIT
