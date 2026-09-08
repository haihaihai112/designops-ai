<div align="center">

# InteriorForge AI

**面向室内设计团队的模型运营工作台**

[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=flat&logo=python&logoColor=white)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green?style=flat)](https://opensource.org/license/mit/)
[![Tests](https://img.shields.io/badge/tests-pytest-0A9ED9?style=flat&logo=pytest&logoColor=white)](tests/)
[![GitHub](https://img.shields.io/badge/GitHub-haihaihai112%2Fdesignops--ai-181717?style=flat&logo=github)](https://github.com/haihaihai112/designops-ai)

</div>

InteriorForge AI 将中文空间需求整理成结构化 Brief、设计知识引用、英文绘图 Prompt 和候选方案。系统会保存自动评分、人工反馈和版本结果，便于比较方案和复盘模型表现。

项目支持两条出图路径：本地 ComfyUI，以及 OpenAI Images API。没有可用的文本模型或图像服务时，系统仍会使用本地模板完成文本链路。

## 快速开始

### Windows

在项目根目录打开 PowerShell：

```powershell
.\install.ps1
python setup_env.py
.\start.ps1
```

安装脚本会创建 `.venv`、安装完整依赖，并准备 `.env`。配置向导会询问文本模型、图像服务和端口。没有 API Key 时可以直接回车，使用本地模板模式。

### Linux 或 macOS

```bash
chmod +x install.sh start.sh
./install.sh
python setup_env.py
./start.sh
```

浏览器打开 <http://127.0.0.1:7860>。

### Docker

需要 Docker 和 Docker Compose：

```bash
cp .env.example .env
docker compose up -d --build
```

浏览器打开 <http://127.0.0.1:7860>。生成结果和 ChromaDB 会保存在宿主机的 `outputs/` 与 `module2_rag/chroma_db/` 目录中。

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

RAG 查询使用语义距离、关键词重合和 MMR 多样性重排。知识库不存在时，首次查询会自动构建；设置 `AUTO_BUILD_KNOWLEDGE_BASE=0` 可以关闭自动构建。生成后的 Prompt 会检查材质、家具和灯光等约束，必要时补充英文别名。

## 配置

所有配置都可以写入 `.env`。也可以运行 `python setup_env.py` 生成配置文件。

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

API Key 只放在 `.env` 或系统环境变量中，不要提交到仓库。

### 图像生成

自动模式会优先检查 ComfyUI，连接失败且配置了 `OPENAI_API_KEY` 时切换到 OpenAI Images API：

```env
IMAGE_PROVIDER=auto
OPENAI_API_KEY=your-openai-api-key
OPENAI_IMAGE_MODEL=gpt-image-1
OPENAI_IMAGE_SIZE=1024x1024
OPENAI_IMAGE_QUALITY=auto
```

只使用 ComfyUI：

```env
IMAGE_PROVIDER=comfyui
COMFYUI_API_BASE=http://127.0.0.1:8188
```

ComfyUI 需要自行准备 checkpoint 和工作流运行环境。没有 GPU 时，可以只启用文本链路，或使用 OpenAI Images API。

### 服务访问

本机访问保持默认值即可。部署到服务器时可以设置：

```env
GRADIO_SERVER_NAME=0.0.0.0
GRADIO_SERVER_PORT=7860
```

如果服务暴露到公网，建议同时设置 `GRADIO_AUTH_USER` 和 `GRADIO_AUTH_PASSWORD`，并在反向代理层配置 HTTPS。

## 户型图生图

工作台的“户型图生图”页支持上传 PNG、JPG 或其他 Pillow 可读取的图片。填写风格、材质和空间要求后，选择视角并生成室内概念效果图。

该功能当前使用 OpenAI Images 的图像编辑接口，需要配置：

```env
OPENAI_API_KEY=your-openai-api-key
IMAGE_PROVIDER=openai
```

系统会先从本地 RAG 知识库检索风格、材质、灯光和家具约束，再将检索结果作为设计参考注入图像编辑提示词。户型图本身是空间布局的最高优先级，提示词会锁定外轮廓、墙体、门窗、房间相邻关系、湿区和动线，RAG 内容不能覆盖这些结构约束。输出结果用于方案概念展示，不能替代施工图或精确尺寸校核。当前 ComfyUI 工作流尚未接入 ControlNet，因此户型图生图页不会调用 ComfyUI。

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

## 项目结构

```text
.
├── config.py                       # LLM、Embedding、服务和图像 API 配置
├── setup_env.py                    # 交互式配置向导
├── install.ps1 / install.sh        # 一键安装脚本
├── start.ps1 / start.sh            # 一键启动脚本
├── Dockerfile                      # Docker 镜像
├── docker-compose.yml              # Docker Compose 配置
├── module1_lora/                   # LoRA 训练数据整理
├── module2_rag/                   # 设计知识库和检索
├── module3_agent/                 # Agent 主流程、评估和出图客户端
├── module4_demo/                  # Gradio 工作台
├── module5_ops/                   # SQLite 存储和报告导出
├── tests/                         # 自动化测试
└── batch_generate.py              # 批量生成示例
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

测试不会调用真实 LLM、Embedding 服务、ComfyUI 或 OpenAI Images API：

```bash
pytest -q
python -m compileall -q module2_rag module3_agent module4_demo module5_ops
```

## 相关链接

- [OpenAI Images API](https://developers.openai.com/api/docs/guides/images-vision)
- [ComfyUI](https://github.com/comfyanonymous/ComfyUI)
- [MIT License](https://opensource.org/license/mit/)

## License

MIT
