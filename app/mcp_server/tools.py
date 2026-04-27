"""MCP tools placeholder implementations."""


def policy_search_tool(query: str, product_name: str, top_k: int = 5) -> dict[str, object]:
    """Return synthetic policy search output."""
    return {
        "tool_name": "policy_search_tool",
        "query": query,
        "product_name": product_name,
        "top_k": top_k,
        "documents": [],
    }
