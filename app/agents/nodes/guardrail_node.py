"""Guardrail node for disclaimer and safety annotations."""

from __future__ import annotations

from app.agents.state import AgentState

DEFAULT_DISCLAIMER = "Synthetic sample response generated without real insurer data or live model calls."
MISSING_CITATION_DISCLAIMER = (
    "This policy-oriented answer does not include supporting citations from the synthetic sample policy, "
    "so it should be treated as a non-authoritative fallback response."
)


def run_guardrail_node(state: AgentState) -> AgentState:
    """Add or strengthen disclaimers for unsupported policy answers."""
    updated = dict(state)
    intent = updated.get("intent")
    citations = updated.get("citations", [])

    if intent in {"policy_qa", "claim_document"} and not citations:
        updated["disclaimer"] = MISSING_CITATION_DISCLAIMER
    else:
        updated["disclaimer"] = DEFAULT_DISCLAIMER

    return updated
