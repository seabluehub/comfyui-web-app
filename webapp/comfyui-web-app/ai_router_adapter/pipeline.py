"""
AIRouterPipeline: Unified Pipeline tying Registries, Supervisor, Router, Assembler, and Executor together.
"""
from typing import Dict, List, Optional, Callable, Any
from .schemas import (
    RouterPipelineOutput,
    SubTaskNode,
    RouteDecision,
    SubTaskExecutionResult,
)
from .registry import ModelRegistry, SkillRegistry, MCPRegistry
from .core import Supervisor, Router, ContextAssembler, SubTaskExecutor


class AIRouterPipeline:
    """
    Main entry point for AI Model, Skill, and MCP Router Adapter.
    """

    def __init__(self, use_mock: bool = True):
        self.model_reg = ModelRegistry()
        self.skill_reg = SkillRegistry()
        self.mcp_reg = MCPRegistry()

        self.supervisor = Supervisor()
        self.router = Router(self.model_reg, self.skill_reg, self.mcp_reg)
        self.assembler = ContextAssembler(self.skill_reg, self.mcp_reg)
        self.executor = SubTaskExecutor(self.mcp_reg, use_mock=use_mock)

    async def run(
        self,
        user_prompt: str,
        on_step_callback: Optional[Callable[[str, Any], None]] = None
    ) -> RouterPipelineOutput:
        """
        Executes the end-to-end routing & orchestration workflow:
        1. Supervisor plans & decomposes user prompt into subtasks.
        2. For each subtask:
           a. Dynamic 3D router selects Model, Skill, and MCP Tools.
           b. Assembler constructs isolated context (Prompt + Skill + Tool Schemas).
           c. Executor runs the Sub-Agent, resolves MCP tool calls, and returns extracted summary.
        3. Supervisor reduces and synthesizes cross-subtask findings into final report.
        """
        if on_step_callback:
            on_step_callback("plan_start", user_prompt)

        # 1. Plan & Decompose
        subtasks = self.supervisor.plan_and_decompose(user_prompt)
        plan_summary = f"Decomposed into {len(subtasks)} coordinated subtasks."

        if on_step_callback:
            on_step_callback("plan_done", subtasks)

        routing_decisions: Dict[str, RouteDecision] = {}
        subtask_results: List[SubTaskExecutionResult] = []
        results_by_id: Dict[str, SubTaskExecutionResult] = {}

        # 2. Sequential / Dependent Execution of Subtasks
        for task in subtasks:
            # a. Route Decision
            decision = self.router.route_subtask(task)
            routing_decisions[task.task_id] = decision

            if on_step_callback:
                on_step_callback("route_decision", decision)

            # b. Context Assembly
            context = self.assembler.assemble(
                task=task,
                decision=decision,
                upstream_results=results_by_id
            )

            if on_step_callback:
                on_step_callback("context_assembled", context)

            # c. Sub-Agent Execution
            exec_res = await self.executor.execute(context, decision)
            subtask_results.append(exec_res)
            results_by_id[task.task_id] = exec_res

            if on_step_callback:
                on_step_callback("subtask_finished", exec_res)

        # 3. Supervisor Synthesizes Final Report
        if on_step_callback:
            on_step_callback("synthesis_start", None)

        final_synthesis = self.supervisor.reduce_and_synthesize(
            user_prompt=user_prompt,
            results=subtask_results
        )

        output = RouterPipelineOutput(
            user_prompt=user_prompt,
            plan_summary=plan_summary,
            subtasks=subtasks,
            routing_decisions=routing_decisions,
            subtask_results=subtask_results,
            final_synthesis=final_synthesis
        )

        if on_step_callback:
            on_step_callback("pipeline_complete", output)

        return output
