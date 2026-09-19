"""
Dynamic Router: Intelligent multi-dimensional matching for Model, Skill, and MCP Tools.
"""
from typing import List, Dict, Tuple
from ..schemas import SubTaskNode, RouteDecision
from ..registry import ModelRegistry, SkillRegistry, MCPRegistry


class Router:
    """
    Intelligent Router that evaluates subtask requirements and selects:
    1. Optimal LLM based on task nature (reasoning, coding, high-speed extraction, general).
    2. Relevant domain Skill(s) to augment system prompt.
    3. Whitelist of necessary MCP tool(s) to avoid token bloat and distraction.
    """

    def __init__(self, model_registry: ModelRegistry, skill_registry: SkillRegistry, mcp_registry: MCPRegistry):
        self.model_reg = model_registry
        self.skill_reg = skill_registry
        self.mcp_reg = mcp_registry

    def route_subtask(self, task: SubTaskNode) -> RouteDecision:
        """Computes the 3-dimensional route decision for a single subtask."""
        selected_model, model_reason = self._select_model(task)
        selected_skills = self._select_skills(task)
        selected_mcp_tools = self._select_mcp_tools(task)

        summary = (
            f"Task '{task.task_id}' -> Model: {selected_model} | "
            f"Skills: {selected_skills or ['None']} | "
            f"MCP Tools: {selected_mcp_tools or ['None']}"
        )

        return RouteDecision(
            task_id=task.task_id,
            selected_model=selected_model,
            model_reason=model_reason,
            selected_skills=selected_skills,
            selected_mcp_tools=selected_mcp_tools,
            routing_summary=summary
        )

    def _select_model(self, task: SubTaskNode) -> Tuple[str, str]:
        """Matches the best model based on task intent and required capabilities using weighted scoring."""
        text = f"{task.title} {task.description}".lower()

        scores = {
            "deepseek-r1": 0,
            "claude-3-7-sonnet": 0,
            "gemini-2.5-flash": 0,
            "gpt-4o": 1  # Base score for generalist
        }

        # 1. Primary capability weights (+10)
        for cap in task.required_capabilities:
            cap_lower = cap.lower()
            if cap_lower in ["reasoning", "logic", "math"]:
                scores["deepseek-r1"] += 10
            elif cap_lower in ["coding", "refactor", "refactoring"]:
                scores["claude-3-7-sonnet"] += 10
            elif cap_lower in ["search", "fast", "retrieval", "extract"]:
                scores["gemini-2.5-flash"] += 10

        # 2. Keyword affinity weights (+2)
        reasoning_keywords = ["complexity", "proof", "logic", "deduction", "deadlock", "race condition"]
        for kw in reasoning_keywords:
            if kw in text:
                scores["deepseek-r1"] += 2

        coding_keywords = ["code", "refactor", "patch", "implementation", "security audit"]
        for kw in coding_keywords:
            if kw in text:
                scores["claude-3-7-sonnet"] += 2

        search_keywords = ["fetch", "search", "pull", "crawl", "retrieve", "realtime", "gather"]
        for kw in search_keywords:
            if kw in text:
                scores["gemini-2.5-flash"] += 2

        # Pick model with highest score
        best_model = max(scores, key=scores.get)

        reasons = {
            "deepseek-r1": "Task requires deep logical deduction, complexity proofs, or formal reasoning.",
            "claude-3-7-sonnet": "Task demands state-of-the-art code refactoring, diff analysis, and reliable tool-use orchestration.",
            "gemini-2.5-flash": "Task prioritizes rapid retrieval, large context ingestion, and low latency tool execution.",
            "gpt-4o": "Task is a balanced general conversation or high-level strategic synthesis."
        }

        return best_model, reasons.get(best_model, "Selected based on requirement scoring.")


    def _select_skills(self, task: SubTaskNode) -> List[str]:
        """Matches domain skills using keyword and tag intersection scoring."""
        text = f"{task.title} {task.description}".lower()
        matched: List[Tuple[str, int]] = []

        for skill in self.skill_reg.list_all():
            score = 0
            for tag in skill.tags:
                if tag in text:
                    score += 2
            # Also check skill description words
            for word in skill.name.lower().split():
                if len(word) > 3 and word in text:
                    score += 1
            if score > 0:
                matched.append((skill.skill_id, score))

        # Sort by score descending and return Top-2
        matched.sort(key=lambda x: x[1], reverse=True)
        return [item[0] for item in matched[:2]]

    def _select_mcp_tools(self, task: SubTaskNode) -> List[str]:
        """Matches specific MCP tools to prevent context oversubscription."""
        text = f"{task.title} {task.description}".lower()
        matched_tools: List[Tuple[str, int]] = []

        for tool in self.mcp_reg.list_all_tools():
            score = 0
            tool_key = f"{tool.server_name}:{tool.tool_name}"
            # Check tool name tokens
            for part in tool.tool_name.split("_"):
                if part in text:
                    score += 3
            # Check tool description keywords
            for word in tool.description.lower().split():
                if len(word) > 3 and word in text:
                    score += 1

            # Specific affinity mappings
            if "pull request" in text or "pr" in text or "github" in text:
                if tool.server_name == "github_mcp":
                    score += 5
            if "search" in text or "web" in text or "lookup" in text or "internet" in text:
                if tool.server_name == "web_search_mcp":
                    score += 5
            if "sql" in text or "database" in text or "query" in text or "table" in text:
                if tool.server_name == "database_mcp":
                    score += 5

            if score >= 3:
                matched_tools.append((tool_key, score))

        matched_tools.sort(key=lambda x: x[1], reverse=True)
        # Limit to top 3 tools max for the subtask context
        return [item[0] for item in matched_tools[:3]]
