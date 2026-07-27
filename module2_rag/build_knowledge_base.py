"""
模块二：设计规范 RAG 知识库 —— 构建脚本

使用方式（只需运行一次）：
    python build_knowledge_base.py

首次运行会自动下载 bge-small-zh-v1.5 嵌入模型（约 100MB），
然后把 design_knowledge/ 下所有 .md 文件切片、向量化、存入 ChromaDB。
"""

import os
import sys
from pathlib import Path

# 国内网络环境：使用 Hugging Face 镜像站
os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"

from config import EMBEDDING_CONFIG, CHROMA_CONFIG, PROJECT_ROOT
from langchain_text_splitters import RecursiveCharacterTextSplitter
from sentence_transformers import SentenceTransformer
import chromadb
from tqdm import tqdm


def load_documents(knowledge_dir: Path) -> list[dict]:
    """加载 design_knowledge/ 下所有 .md 文件，返回 [{path, content}]"""
    docs = []
    for md_file in sorted(knowledge_dir.glob("*.md")):
        with open(md_file, "r", encoding="utf-8") as f:
            content = f.read()
        if content.strip():
            docs.append({"path": str(md_file.name), "content": content})
    return docs


def split_documents(docs: list[dict]) -> list[dict]:
    """
    递归字符切片器：优先按 ## 标题切，保证每个 chunk 语义完整。
    chunk_size=512, overlap=64 对中文设计文档比较合适。
    """
    splitter = RecursiveCharacterTextSplitter(
        separators=["\n## ", "\n### ", "\n#### ", "\n", "。", "；", "，", " ", ""],
        chunk_size=512,
        chunk_overlap=64,
        length_function=len,
    )

    chunks = []
    for doc in docs:
        texts = splitter.split_text(doc["content"])
        for i, text in enumerate(texts):
            if len(text.strip()) < 20:  # 跳过太短的碎片
                continue
            chunks.append({
                "source": doc["path"],
                "chunk_index": i,
                "text": text.strip(),
            })

    print(f"  {len(docs)} 个文档 → {len(chunks)} 个切片")
    return chunks


def build_index(chunks: list[dict]):
    """向量化 + 存入 ChromaDB"""
    print(f"\n[2/3] 加载嵌入模型: {EMBEDDING_CONFIG['model_name']}")
    model = SentenceTransformer(
        EMBEDDING_CONFIG["model_name"],
        device=EMBEDDING_CONFIG["device"],
    )

    print(f"  正在向量化 {len(chunks)} 个切片...")
    texts = [c["text"] for c in chunks]
    embeddings = model.encode(
        texts,
        show_progress_bar=True,
        normalize_embeddings=True,  # 余弦相似度用归一化
    )

    print(f"\n[3/3] 存入 ChromaDB: {CHROMA_CONFIG['persist_directory']}")
    client = chromadb.PersistentClient(path=CHROMA_CONFIG["persist_directory"])

    # 如果 collection 已存在，删除重建
    try:
        client.delete_collection(CHROMA_CONFIG["collection_name"])
    except Exception:
        pass

    collection = client.create_collection(
        name=CHROMA_CONFIG["collection_name"],
        metadata={"description": "室内设计规范知识库 —— 侘寂风、法式奶油风、灯光标准、材质PBR"},
    )

    # 批量插入
    batch_size = 100
    for i in tqdm(range(0, len(chunks), batch_size), desc="  写入 ChromaDB"):
        batch = chunks[i:i + batch_size]
        collection.add(
            ids=[f"chunk_{j}" for j in range(i, i + len(batch))],
            embeddings=embeddings[i:i + batch_size].tolist(),
            documents=[c["text"] for c in batch],
            metadatas=[{"source": c["source"], "chunk_index": c["chunk_index"]} for c in batch],
        )

    print(f"\n✅ 知识库构建完成！共 {collection.count()} 条记录")
    print(f"  数据库路径: {CHROMA_CONFIG['persist_directory']}")
    return collection


def main():
    knowledge_dir = PROJECT_ROOT / "module2_rag" / "design_knowledge"

    print("=" * 60)
    print("室内设计规范 RAG 知识库构建")
    print("=" * 60)

    print(f"\n[1/3] 加载文档: {knowledge_dir}")
    docs = load_documents(knowledge_dir)
    if not docs:
        print("❌ 没有找到任何 .md 文档，请检查 design_knowledge/ 目录")
        sys.exit(1)
    print(f"  找到 {len(docs)} 个文档: {[d['path'] for d in docs]}")

    chunks = split_documents(docs)
    build_index(chunks)


if __name__ == "__main__":
    main()
