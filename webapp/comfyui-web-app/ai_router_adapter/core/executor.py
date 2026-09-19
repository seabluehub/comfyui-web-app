"""
SubTask Executor: Runs subtasks against designated models with MCP tool invocation loop.
"""
import json
from typing import Dict, Any, List, Optional
from ..schemas import AssembledContext, SubTaskExecutionResult, RouteDecision
from ..registry import MCPRegistry


class SubTaskExecutor:
    """
    Executes a subtask using the assembled context.
    Manages the multi-turn tool-calling loop with MCP servers.
    """

    def __init__(self, mcp_registry: MCPRegistry, use_mock: bool = True):
        self.mcp_reg = mcp_registry
        self.use_mock = use_mock

    async def execute(
        self,
        context: AssembledContext,
        decision: RouteDecision
    ) -> SubTaskExecutionResult:
        """Executes the subtask and handles any tool calls."""
        if self.use_mock:
            return await self._mock_execute(context, decision)
        else:
            return await self._live_execute(context, decision)

    async def _mock_execute(
        self,
        context: AssembledContext,
        decision: RouteDecision
    ) -> SubTaskExecutionResult:
        """Simulates high-fidelity execution for different models, skills, and tools."""
        tools_called: List[Dict[str, Any]] = []

        # If tools are available, simulate tool calls
        if context.available_tools:
            for tool_def in context.available_tools:
                fn_name = tool_def["function"]["name"]
                parts = fn_name.split(":")
                server_name = parts[0]
                tool_name = parts[1] if len(parts) > 1 else parts[0]

                # Mock tool call args based on context
                args = {}
                if "pull_request" in tool_name:
                    args = {"repo": "enterprise/core-algo", "pr_number": 308}
                elif "search" in tool_name:
                    args = {"query": "Python 3.13 concurrency parallel merge sort"}
                elif "sql" in tool_name:
                    args = {"query": "SELECT count(*) FROM latency_logs"}

                tool_result = self.mcp_reg.execute_tool(server_name, tool_name, args)
                tools_called.append({
                    "tool": fn_name,
                    "arguments": args,
                    "result": tool_result
                })

        # Generate realistic output conditioned on the model and skills
        model_id = context.selected_model
        skills = decision.selected_skills

        if model_id == "deepseek-r1":
            raw_output = (
                f"[Model: {model_id} | Formal Reasoning & Complexity Analysis]\n"
                "- Algorithmic Correctness: ParallelMergeSort divides array into k chunks. O(N log(N/k)) parallel chunk sort + O(N log k) multi-way merge.\n"
                "- Concurrency Risk Identified: ThreadPoolExecutor submission creates unbound futures without backpressure if chunk_size is too small.\n"
                "- Proof of Deadlock/Contention: When merge_chunks accesses a shared list without lock synchronization in multi-threaded runtime, data corruption or race condition occurs at boundary indices.\n"
                "- Recommendation: Use lockless double-buffering or thread-local storage for chunk outputs."
            )
            extracted = "Found concurrency race hazard in chunk accumulation; verified theoretical time complexity at O(N log N) with parallel speedup ceiling k."

        elif model_id == "claude-3-7-sonnet":
            raw_output = (
                f"[Model: {model_id} | Code Audit & Refactoring Implementation]\n"
                "Refactored sorting implementation with defensive thread safety:\n"
                "```python\n"
                "from concurrent.futures import ProcessPoolExecutor\n"
                "import heapq\n\n"
                "def safe_parallel_merge_sort(arr: list, workers: int = 4) -> list:\n"
                "    if len(arr) <= 1024:\n"
                "        return sorted(arr)\n"
                "    chunk_size = (len(arr) + workers - 1) // workers\n"
                "    chunks = [arr[i:i + chunk_size] for i in range(0, len(arr), chunk_size)]\n"
                "    with ProcessPoolExecutor(max_workers=workers) as executor:\n"
                "        sorted_chunks = list(executor.map(sorted, chunks))\n"
                "    return list(heapq.merge(*sorted_chunks))\n"
                "```\n"
                "- Replaced ThreadPoolExecutor with ProcessPoolExecutor to bypass GIL and eliminate shared state contention.\n"
                "- Integrated `heapq.merge` for O(N log k) memory-efficient streaming merge."
            )
            extracted = "Delivered production-ready thread-safe refactor using ProcessPoolExecutor and heapq.merge; eliminated shared memory lock contention."

        elif model_id == "gemini-2.5-flash":
            tool_info = json.dumps([t["tool"] for t in tools_called]) if tools_called else "None"
            raw_output = (
                f"[Model: {model_id} | High-Speed Data Retrieval & Synthesis]\n"
                f"- Successfully called MCP Tools: {tool_info}\n"
                "- Extracted PR #308 metadata: Author dev-lead, modified `algorithms/sort.py` (+45, -12 lines).\n"
                "- Code diff shows ThreadPoolExecutor introduced to parallelize chunk sorting."
            )
            extracted = f"Retrieved PR #308 diff and metadata via {tool_info} in 210ms."

        else:
            raw_output = (
                f"[Model: {model_id} | Generalist Evaluation]\n"
                "Analyzed task requirements and synthesized contextual response."
            )
            extracted = "Completed task evaluation."

        return SubTaskExecutionResult(
            task_id=context.task_id,
            status="success",
            model_used=model_id,
            skills_loaded=skills,
            mcp_tools_called=tools_called,
            extracted_summary=extracted,
            raw_output=raw_output
        )

    async def _live_execute(
        self,
        context: AssembledContext,
        decision: RouteDecision
    ) -> SubTaskExecutionResult:
        """Fallback to mock or live API when available."""
        # For now, default to mock implementation
        return await self._mock_execute(context, decision)
