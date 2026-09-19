"""
Model Registry: Catalogs available LLMs and their capabilities, speeds, costs.
"""
from typing import Dict, List, Optional
from ..schemas import ModelProfile


class ModelRegistry:
    """Manages the available AI models in the ecosystem."""

    def __init__(self):
        self._models: Dict[str, ModelProfile] = {}
        self._register_default_models()

    def _register_default_models(self):
        defaults = [
            ModelProfile(
                model_id="deepseek-r1",
                provider="deepseek",
                capabilities=["reasoning", "math", "logic", "deep_analysis"],
                context_window=128000,
                cost_tier="low",
                speed_tier="slow",
                description="Specialized in deep multi-step mathematical reasoning, formal logic, and complex architectural trade-offs."
            ),
            ModelProfile(
                model_id="claude-3-7-sonnet",
                provider="anthropic",
                capabilities=["coding", "agentic_workflow", "tool_use", "refactoring"],
                context_window=200000,
                cost_tier="high",
                speed_tier="medium",
                description="Industry-leading code generation, diff analysis, multi-file refactoring, and accurate tool-use orchestration."
            ),
            ModelProfile(
                model_id="gemini-2.5-flash",
                provider="google",
                capabilities=["fast", "cheap", "search", "summarization", "multimodal"],
                context_window=1000000,
                cost_tier="lowest",
                speed_tier="fast",
                description="Ultra-fast, ultra-large context model ideal for fast data extraction, web search synthesis, and JSON extraction."
            ),
            ModelProfile(
                model_id="gpt-4o",
                provider="openai",
                capabilities=["general", "creative", "multimodal", "tool_use"],
                context_window=128000,
                cost_tier="medium",
                speed_tier="medium",
                description="Well-balanced generalist model for natural language synthesis, report writing, and general conversational tasks."
            ),
        ]
        for m in defaults:
            self.register(m)

    def register(self, profile: ModelProfile):
        self._models[profile.model_id] = profile

    def get(self, model_id: str) -> Optional[ModelProfile]:
        return self._models.get(model_id)

    def list_all(self) -> List[ModelProfile]:
        return list(self._models.values())
