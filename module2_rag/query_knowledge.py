"""
模块二：RAG 知识库 —— 查询接口

使用方式：
    python query_knowledge.py "侘寂风的灯光色温应该是多少"

或作为模块导入：
    from module2_rag.query_knowledge import query_design_knowledge
    results = query_design_knowledge("侘寂风客厅的材质选择")
"""

import os
import sys
from pathlib import Path

# 国内网络环境：使用 Hugging Face 镜像站
os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import EMBEDDING_CONFIG, CHROMA_CONFIG
# 全局缓存，避免每次查询都重新加载
_embedding_model = None
_chroma_collection = None


def _get_embedding_model():
    global _embedding_model
    if _embedding_model is None:
        from sentence_transformers import SentenceTransformer

        _embedding_model = SentenceTransformer(
            EMBEDDING_CONFIG["model_name"],
            device=EMBEDDING_CONFIG["device"],
            config_kwargs={"local_files_only": True},  # 仅用本地缓存，不联网
        )
    return _embedding_model


def _get_collection():
    global _chroma_collection
    if _chroma_collection is None:
        import chromadb

        client = chromadb.PersistentClient(path=CHROMA_CONFIG["persist_directory"])
        _chroma_collection = client.get_collection(CHROMA_CONFIG["collection_name"])
    return _chroma_collection


def query_design_knowledge(query: str, top_k: int = 5) -> list[dict]:
    """
    查询设计知识库。

    参数:
        query: 中文查询文本（如 "侘寂风墙面用什么材料"）
        top_k: 返回最相似的前 K 个结果

    返回:
        [{text, source, distance}, ...]
        - text: 匹配的知识片段
        - source: 来源文档名
        - distance: 向量距离（越小越相关）
    """
    model = _get_embedding_model()
    collection = _get_collection()

    # 向量化查询
    query_embedding = model.encode(
        [query],
        normalize_embeddings=True,
    ).tolist()

    # 检索
    results = collection.query(
        query_embeddings=query_embedding,
        n_results=top_k,
    )

    # 整理输出
    formatted = []
    for i in range(len(results["ids"][0])):
        formatted.append({
            "text": results["documents"][0][i],
            "source": results["metadatas"][0][i]["source"],
            "distance": results["distances"][0][i] if results["distances"] else None,
        })

    return formatted


def format_results(query: str, results: list[dict]) -> str:
    """将检索结果格式化为可读文本，供 Agent 使用"""
    lines = [f"📚 知识库检索结果（查询: {query}）\n"]
    for i, r in enumerate(results, 1):
        distance_str = f"{r['distance']:.4f}" if r['distance'] else "N/A"
        lines.append(f"--- 结果 {i} (来源: {r['source']}, 距离: {distance_str}) ---")
        lines.append(r["text"][:300])  # 截断过长内容
        lines.append("")
    return "\n".join(lines)


def build_citations(results: list[dict]) -> list[dict]:
    """Return compact citation records that can be persisted and rendered by the UI."""
    citations = []
    for index, result in enumerate(results, 1):
        citations.append({
            "index": index,
            "source": result["source"],
            "excerpt": result["text"][:240].strip(),
            "distance": round(result["distance"], 4) if result["distance"] is not None else None,
        })
    return citations


# CLI 入口
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python query_knowledge.py <查询文本>")
        print('示例: python query_knowledge.py "侘寂风客厅适合用什么灯光"')
        sys.exit(1)

    query = " ".join(sys.argv[1:])
    print(f"🔍 查询: {query}\n")

    results = query_design_knowledge(query, top_k=5)
    print(format_results(query, results))
