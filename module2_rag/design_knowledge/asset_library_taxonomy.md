# 家居模型素材库运营标签体系

## 素材库目标
模型素材库不是简单堆资源，而是让设计师能快速检索、复用和组合家具、材质、灯具、装饰品。素材入库时需要同时考虑风格、空间、品类、材质、颜色、尺寸、适用场景和质量状态。

## 核心字段
- asset_id：唯一编号。
- asset_name_en：英文名称，如 boucle sofa, travertine coffee table。
- asset_name_zh：中文名称，如 羊羔绒沙发、洞石茶几。
- category：sofa, bed, dining chair, pendant lamp, wall art, rug, plant。
- room_type：living room, bedroom, dining room, kitchen, bathroom, study。
- style_tags：wabi-sabi, french cream, minimalist, modern luxury, scandinavian。
- material_tags：oak wood, walnut, linen, velvet, brass, travertine, microcement。
- color_tags：cream, warm white, greige, walnut brown, matte black, muted green。
- quality_score：1-5 分，综合模型精度、贴图质量、比例准确度。
- source：self-made, vendor, public library, generated, curated。
- license_status：commercial safe, internal only, unknown。
- coohom_keywords：在 Coohom / Kujiale 中检索时使用的英文关键词。

## 入库质量标准
- 模型比例正确，常见家具需符合人体工学尺度。
- 贴图清晰，无明显拉伸、重复或水印。
- 法线、粗糙度、金属度等 PBR 信息尽量完整。
- 文件命名统一，英文关键词可被海外团队理解。
- 同一风格下形成系列组合，而不是孤立单品。

## 推荐标签组合
- 侘寂风：wabi-sabi, japandi, natural wood, linen, ceramic, paper lamp, earth tone。
- 法式奶油风：french cream, arched, plaster molding, boucle, brass, herringbone floor。
- 极简无主灯：minimalist, microcement, magnetic track light, hidden storage, linear light。
- 现代轻奢：modern luxury, marble, brushed brass, leather, glass, warm grey。
- 北欧自然风：scandinavian, oak wood, cotton linen, rattan, soft white, indoor plants。
