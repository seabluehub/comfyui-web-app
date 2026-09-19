"""
Core schemas and data models for AI Router Adapter.
"""
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class ModelProfile(BaseModel):
    """Profile describing an AI Model and its traits."""
    model_id: str
    provider: str
    capabilities: List[str] = Field(default_factory=list, description="Capabilities: reasoning, coding, search, fast, cheap, multimodal")
    context_window: int = 128000
    cost_tier: str = "medium"  # lowest, low, medium, high
    speed_tier: str = "medium"  # fast, medium, slow
    description: str = ""


class SkillProfile(BaseModel):
    """Profile describing an injectable domain skill."""
    skill_id: str
    name: str
    description: str
    tags: List[str] = Field(default_factory=list)
    system_prompt_template: str


class MCPToolParameter(BaseModel):
    name: str
    type: str
    description: str
    required: bool = True


class MCPToolSpec(BaseModel):
    """Specification of an MCP Tool."""
    tool_name: str
    server_name: str
    description: str
    parameters: Dict[str, Any] = Field(default_factory=dict)


class MCPServerSpec(BaseModel):
    """Specification of an MCP Server with its tools."""
    server_name: str
    description: str
    tools: List[MCPToolSpec] = Field(default_factory=list)


class SubTaskNode(BaseModel):
    """A subtask decomposed by the supervisor."""
    task_id: str
    title: str
    description: str
    depends_on: List[str] = Field(default_factory=list)
    required_capabilities: List[str] = Field(default_factory=list)


class RouteDecision(BaseModel):
    """Routing decision for a specific subtask."""
    task_id: str
    selected_model: str
    model_reason: str
    selected_skills: List[str] = Field(default_factory=list)
    selected_mcp_tools: List[str] = Field(default_factory=list, description="Format: server_name:tool_name")
    routing_summary: str


class AssembledContext(BaseModel):
    """Complete assembled context ready to be fed to the selected LLM."""
    task_id: str
    selected_model: str
    system_prompt: str
    user_prompt: str
    available_tools: List[Dict[str, Any]] = Field(default_factory=list)


class SubTaskExecutionResult(BaseModel):
    """Result of executing a single subtask."""
    task_id: str
    status: str = "success"  # success, failed
    model_used: str
    skills_loaded: List[str] = Field(default_factory=list)
    mcp_tools_called: List[Dict[str, Any]] = Field(default_factory=list)
    extracted_summary: str
    raw_output: str


class RouterPipelineOutput(BaseModel):
    """Final unified output from the entire pipeline."""
    user_prompt: str
    plan_summary: str
    subtasks: List[SubTaskNode]
    routing_decisions: Dict[str, RouteDecision]
    subtask_results: List[SubTaskExecutionResult]
    final_synthesis: str
