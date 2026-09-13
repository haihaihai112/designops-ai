"""Read-only design tools and an optional smolagents orchestration entrypoint."""

from __future__ import annotations

import json

from config import LLM_CONFIG
from module2_rag.query_knowledge import build_citations, query_design_knowledge, rerank_results
from module3_agent.quality_evaluator import evaluate_design_bundle
from module3_agent.requirement_parser import parse_design_requirement


def parse_design_brief(requirement: str) -> str:
    """Parse a Chinese interior-design request into a structured JSON brief.

    Args:
        requirement: The user's complete interior-design request.

    Returns:
        A JSON object containing room, style, area, and hard constraints.
    """
    return json.dumps(parse_design_requirement(requirement), ensure_ascii=False)


def search_design_knowledge(query: str) -> str:
    """Search the local interior-design knowledge base and return cited passages.

    Args:
        query: A focused question about materials, lighting, layout, or style.

    Returns:
        JSON containing compact source citations and excerpts.
    """
    results = query_design_knowledge(query, top_k=8)
    ranked = rerank_results(query, results, top_k=4)
    return json.dumps(build_citations(ranked), ensure_ascii=False)


def score_design_prompt(requirement: str, positive_prompt: str) -> str:
    """Score how well an English image prompt covers a Chinese design request.

    Args:
        requirement: The original Chinese design request.
        positive_prompt: The proposed English image-generation prompt.

    Returns:
        JSON with explainable quality scores and missing constraints.
    """
    parsed = parse_design_requirement(requirement)
    bundle = {
        "positive_prompt": positive_prompt,
        "analysis": "agent draft",
        "coohom_brief": "agent draft",
        "asset_tags": "agent draft",
        "social_copy": "agent draft",
    }
    return json.dumps(evaluate_design_bundle(parsed, bundle), ensure_ascii=False)


def run_design_tool_agent(user_input: str, max_steps: int = 6) -> str:
    """Run a read-only ToolCallingAgent over parsing, RAG, and evaluation tools."""
    try:
        from smolagents import LiteLLMModel, ToolCallingAgent, tool
    except ImportError as exc:
        raise RuntimeError(
            "工具 Agent 需要安装 requirements-aiops.txt"
        ) from exc

    model = LiteLLMModel(
        model_id=LLM_CONFIG["litellm_model"],
        api_base=LLM_CONFIG["api_base"],
        api_key=LLM_CONFIG["api_key"],
        temperature=LLM_CONFIG["temperature"],
    )
    tools = [
        tool(parse_design_brief),
        tool(search_design_knowledge),
        tool(score_design_prompt),
    ]
    agent = ToolCallingAgent(tools=tools, model=model, max_steps=max_steps)
    task = (
        "You are an interior-design planning agent. Use the tools to parse the request, "
        "retrieve relevant local knowledge with citations, draft an English positive image "
        "prompt, and score it. Revise once when important constraints are missing. Return a "
        "concise Chinese explanation, the final English prompt, citations, and quality score.\n\n"
        f"User request: {user_input}"
    )
    return str(agent.run(task))


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        raise SystemExit("用法: python -m module3_agent.tool_agent <设计需求>")
    print(run_design_tool_agent(" ".join(sys.argv[1:])))
