"""Workflow agent graph placeholder."""

from app.agents.state import AgentState


def run_workflow(state: AgentState) -> AgentState:
    """Run a synthetic workflow and return updated state."""
    updated = dict(state)
    updated.setdefault("intent", "unknown")
    updated.setdefault("answer", "Workflow placeholder response")
    return updated
