"""
Context Assembler: Formats system prompt, skill instructions, and MCP tool schemas.
"""
from typing import Dict, List, Any, Optional
from ..schemas import SubTaskNode, RouteDecision, AssembledContext, SubTaskExecutionResult
from ..registry import SkillRegistry, MCPRegistry


class ContextAssembler:
    """
    Assembles a streamlined, isolated context for a Sub-Agent:
    - Injects matching Skill prompts into System Prompt.
    - Extracts matching MCP tool JSON schemas (filtered by whitelist).
    - Injects upstream dependency outputs into User Prompt.
    """

    def __init__(self, skill_registry: SkillRegistry, mcp_registry: MCPRegistry):
        self.skill_reg = skill_registry
        self.mcp_reg = mcp_registry

    def assemble(
        self,
        task: SubTaskNode,
        decision: RouteDecision,
        upstream_results: Optional[Dict[str, SubTaskExecutionResult]] = None
    ) -> AssembledContext:
        # 1. Build Base System Prompt + Skills
        sys_prompt_lines = [
            f"You are a specialized autonomous Sub-Agent assigned to execute task [{task.task_id}].",
            f"Objective: {task.title}",
            "Follow domain-specific best practices, call provided tools when necessary, and output concise results.",
            ""
        ]

        if decision.selected_skills:
            sys_prompt_lines.append("## Activated Skills & Guidelines:")
            for s_id in decision.selected_skills:
                skill = self.skill_reg.get(s_id)
                if skill:
                    sys_prompt_lines.append(skill.system_prompt_template.strip())
            sys_prompt_lines.append("")

        # 2. Build User Prompt with upstream context
        user_prompt_lines = [
            f"### Task Instructions for [{task.task_id}]:",
            task.description,
            ""
        ]

        if task.depends_on and upstream_results:
            user_prompt_lines.append("### Context from Prior Dependent Subtasks:")
            for dep_id in task.depends_on:
                if dep_id in upstream_results:
                    res = upstream_results[dep_id]
                    user_prompt_lines.append(f"#### Result from [{dep_id}] (Model: {res.model_used}):")
                    user_prompt_lines.append(res.extracted_summary)
                    user_prompt_lines.append("")

        # 3. Format Tools (OpenAI function calling schema standard)
        tools_schema: List[Dict[str, Any]] = []
        for tool_key in decision.selected_mcp_tools:
            parts = tool_key.split(":")
            if len(parts) == 2:
                server_name, tool_name = parts
                tool_spec = self.mcp_reg.get_tool(server_name, tool_name)
                if tool_spec:
                    tools_schema.append({
                        "type": "function",
                        "function": {
                            "name": tool_key,  # namespace with server:tool
                            "description": tool_spec.description,
                            "parameters": tool_spec.parameters
                        }
                    })

        return AssembledContext(
            task_id=task.task_id,
            selected_model=decision.selected_model,
            system_prompt="\n".join(sys_prompt_lines),
            user_prompt="\n".join(user_prompt_lines),
            available_tools=tools_schema
        )
