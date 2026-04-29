"""Dependency container for the workflow agent."""

from __future__ import annotations

from dataclasses import dataclass

from app.mcp_server.tools.design_condition_tool import DesignConditionTool
from app.mcp_server.tools.policy_search_tool import PolicySearchTool
from app.mcp_server.tools.product_recommend_tool import ProductRecommendTool
from app.rag.generator import WorkflowAnswerGenerator
from app.services.firestore_service import FirestoreService


@dataclass
class WorkflowDependencies:
    """Concrete dependencies used by workflow nodes."""

    policy_search_tool: PolicySearchTool
    product_recommend_tool: ProductRecommendTool
    design_condition_tool: DesignConditionTool
    answer_generator: WorkflowAnswerGenerator
    firestore_service: FirestoreService
