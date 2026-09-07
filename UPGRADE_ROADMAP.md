# InteriorForge AI 迭代升级路线

> 适用于后续对话、开发任务拆分和版本复盘。当前项目路径：
> `C:\Users\38241\Desktop\简历\项目\InteriorForge AI｜室内设计模型运营智能体`

## 1. 当前基线

当前链路：

```text
中文需求
  -> 结构化解析
  -> RAG 检索
  -> LLM / 本地模板生成 Prompt
  -> Prompt 约束修复
  -> ComfyUI 或 OpenAI Images API 出图
  -> 自动质量评分
  -> 人工反馈与 SQLite 看板
```

已完成的迭代：

- RAG 增加关键词相关性和 MMR 多样性重排，降低相同来源片段重复。
- Prompt 增加确定性自修复，自动补齐材质、家具、灯光等硬约束。
- 风格别名评分修复，例如 `wabi-sabi`、`wabisabi`、`japandi` 统一识别。
- 图像生成增加 `comfyui`、`openai`、`auto` 三种 provider。
- OpenAI Images API 返回的 base64 和 URL 两种结果都可以保存到 `outputs/api/`。
- 现有自动化测试和 Python 编译检查保持通过。

## 2. 图像生成 API 使用方式

### 安装

在当前项目路径执行：

```powershell
cd "C:\Users\38241\Desktop\简历\项目\InteriorForge AI｜室内设计模型运营智能体"
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

在 `.env` 中填写：

```env
IMAGE_PROVIDER=openai
OPENAI_API_KEY=your-openai-api-key
OPENAI_IMAGE_MODEL=gpt-image-1
OPENAI_IMAGE_SIZE=1024x1024
OPENAI_IMAGE_QUALITY=auto
```

安全要求：不要把真实 Key 提交到 Git；`.env` 已被 `.gitignore` 排除。OpenAI 官方图像接口说明：
<https://developers.openai.com/api/docs/guides/images-vision>

### 调用示例

```python
from module3_agent.agent_pipeline import run_agent

result = run_agent(
    "25平米侘寂风客厅，亚麻沙发、原木茶几、落地窗、暖光",
    generate=True,
    image_provider="openai",
)
print(result["image"])
```

provider 选择：

| Provider | 适用场景 | 依赖 |
| --- | --- | --- |
| `comfyui` | 本地 GPU、ControlNet、LoRA、自定义工作流 | ComfyUI 服务 |
| `openai` | 快速验证、无本地 GPU、低运维 | `OPENAI_API_KEY` |
| `auto` | 生产演示和故障转移 | 两者至少配置一个 |

## 3. 分阶段升级计划

### P0：稳定性和可观测性

- 为每次生成写入 `provider`、模型、请求耗时、失败原因和成本字段。
- 增加 API 重试：仅对网络错误、429、5xx 使用指数退避；参数错误不重试。
- 为 Prompt、RAG 引用和图片结果生成 `request_id`，便于追踪一轮迭代。
- 增加 provider 级成功率、P50/P95 延迟、兜底率、平均成本看板。
- 对生成图片做文件大小、格式和可读性校验，避免坏图进入项目库。

验收指标：API 成功率、平均生成耗时、失败可解释率、`auto` 自动切换成功率。

### P1：检索和 Prompt 质量

- 将当前轻量词法匹配升级为 Dense Embedding + BM25 的混合召回。
- 对召回结果增加 Cross-Encoder 重排，并保留 MMR 去重。
- 将用户需求拆成硬约束、软偏好和禁止项，分别注入 Prompt。
- 增加生成后自检：房间、风格、材质、家具、灯光、面积覆盖率。
- 对低于质量阈值的 Prompt 自动进行一次修复，记录修复前后分数。

验收指标：需求覆盖率、意图一致性、RAG 引用命中率、人工采用率。

### P1：图像质量评估

- 使用 CLIP 或 DINOv2 计算图像与需求文本/参考图的相似度。
- 使用轻量审美模型评估构图、清晰度、曝光和视觉完整性。
- 增加 OCR/水印检测、黑图检测和分辨率检测。
- 将自动质量分和人工评分分开保存，避免自动分掩盖模型偏差。

推荐评分组合：

```text
最终排序分 = 需求一致性 * 0.35
           + 图文相似度 * 0.25
           + 视觉质量 * 0.20
           + 落地可行性 * 0.20
```

### P2：反馈学习和候选选择

- 将“采用、保留、淘汰”和三项人工评分转为偏好数据集。
- 先使用离线 pairwise ranking 训练候选排序器，再考虑 DPO/ORPO 优化 LLM 输出。
- 对 `balanced`、`creative`、`practical` 使用 contextual bandit 动态分配候选比例。
- 保留探索比例，避免系统只生成已有风格，导致策略塌缩。

触发条件：至少积累 200 条有完整人工反馈的候选记录后再训练排序器。

### P2：空间结构与多视角一致性

- ComfyUI 路线增加 ControlNet Depth/Canny，约束墙体、门窗和家具轮廓。
- 参考图场景使用 IP-Adapter，控制材质和风格迁移。
- 多视角方案增加固定 seed、固定结构条件和房间级 latent 记录。
- 将面积、动线、家具尺寸转为可检查的几何约束，而不是只放入自然语言 Prompt。

验收指标：多视角风格一致性、结构保持率、家具尺度错误率。

### P3：LoRA 与数据闭环

- 仅收集人工采用或高评分方案，过滤失败图和版权不明素材。
- 使用 caption 标准化：空间、风格、材质、灯光、镜头、质量标签分字段维护。
- 优先 QLoRA/LoRA 做风格或企业资产适配，不在小数据上全量微调基础模型。
- 每轮训练保留固定验证集，比较基线、上一版和当前版的覆盖率与人工采用率。

## 4. 建议的迭代顺序

```text
第 1 周：API 重试、请求追踪、provider 指标
第 2 周：混合检索、Cross-Encoder 重排
第 3 周：CLIP/DINOv2 图像评估和坏图检测
第 4 周：反馈数据集、候选排序器、离线评测集
第 5 周以后：ControlNet/IP-Adapter、多视角一致性、LoRA 训练
```

## 5. 每轮迭代必须保留的实验记录

- 代码版本和配置版本。
- 输入需求和结构化 Brief。
- RAG 文档、距离、重排分数和最终引用。
- Prompt 原文、修复项和最终 Prompt。
- provider、模型、参数、seed、耗时和错误信息。
- 自动评分、人工评分、最终决策。
- 与上一版本相比的指标变化。

## 6. 下一次对话可直接使用的任务模板

```text
请在项目
C:\Users\38241\Desktop\简历\项目\InteriorForge AI｜室内设计模型运营智能体
中继续执行 UPGRADE_ROADMAP.md 的 [填写阶段/任务]。

要求：
1. 先阅读当前实现和测试；
2. 保持 ComfyUI、OpenAI API 和离线模板三条路径兼容；
3. 先新增测试，再改实现；
4. 不写入真实 API Key；
5. 完成后运行 pytest 和 compileall，并报告指标变化。
```
