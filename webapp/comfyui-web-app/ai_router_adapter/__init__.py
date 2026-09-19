"""
AI Router Adapter: Intelligent dynamic model, skill, and MCP router & orchestrator.
"""
from .pipeline import AIRouterPipeline
from .schemas import (
    RouterPipelineOutput,
    SubTaskNode,
    RouteDecision,
    SubTaskExecutionResult,
    ModelProfile,
    SkillProfile,
    MCPToolSpec
)

__all__ = [
    "AIRouterPipeline",
    "RouterPipelineOutput",
    "SubTaskNode",
    "RouteDecision",
    "SubTaskExecutionResult",
    "ModelProfile",
    "SkillProfile",
    "MCPToolSpec"
]
