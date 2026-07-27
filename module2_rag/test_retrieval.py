"""手动检查知识库检索结果。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from module2_rag.query_knowledge import format_results, query_design_knowledge


def main():
    queries = [
        "侘寂风的特点是什么？",
        "法式奶油风的配色方案",
        "灯光照度标准",
        "PBR 材质参数",
    ]

    for query in queries:
        print(f"\n{'=' * 60}\n查询：{query}\n{'=' * 60}")
        print(format_results(query, query_design_knowledge(query, top_k=2)))


if __name__ == "__main__":
    main()
