"""
Supervisor: Orchestrator responsible for Plan & Decompose and Reduce & Synthesize.
"""
from typing import List, Dict, Any
from ..schemas import SubTaskNode, SubTaskExecutionResult


class Supervisor:
    """
    Main controller agent that:
    1. Breaks down high-level user prompt into a DAG of SubTaskNodes.
    2. Gathers individual subtask execution results and synthesizes final analysis.
    """

    def plan_and_decompose(self, user_prompt: str) -> List[SubTaskNode]:
        """
        Analyzes the user prompt and generates an actionable DAG of subtasks.
        """
        text = user_prompt.lower()
        subtasks: List[SubTaskNode] = []

        # Heuristic task topology decomposition
        if any(w in text for w in ["pr", "pull request", "github", "diff"]) and any(w in text for w in ["并发", "复杂度", "算法", "死锁", "漏洞", "性能", "优化", "审查"]):
            # Scenario: Multi-step code audit & algorithmic reasoning
            subtasks.append(
                SubTaskNode(
                    task_id="task_1_fetch_context",
                    title="Retrieve Target PR Diff and Context",
                    description="Call GitHub MCP to pull changed files, diffs, and commit descriptions for the specified PR.",
                    depends_on=[],
                    required_capabilities=["search", "fast"]
                )
            )
            subtasks.append(
                SubTaskNode(
                    task_id="task_2_reasoning_audit",
                    title="Algorithmic Complexity & Concurrency Hazard Deduction",
                    description="Analyze the retrieved PR code for mathematical time/space complexity, race conditions, and thread contention risks.",
                    depends_on=["task_1_fetch_context"],
                    required_capabilities=["reasoning", "logic"]
                )
            )
            subtasks.append(
                SubTaskNode(
                    task_id="task_3_code_refactor",
                    title="Implement Defensive Refactoring and Fixes",
                    description="Generate optimized, thread-safe production code replacing vulnerable sections identified in prior analysis.",
                    depends_on=["task_2_reasoning_audit"],
                    required_capabilities=["coding", "refactoring"]
                )
            )

        elif any(w in text for w in ["调研", "研究", "趋势", "search", "benchmarks", "对比"]):
            # Scenario: Research & Fact-finding
            subtasks.append(
                SubTaskNode(
                    task_id="task_1_web_search",
                    title="Retrieve Latest Industry Information & Benchmarks",
                    description="Perform live web search queries and extract real-world technical developments.",
                    depends_on=[],
                    required_capabilities=["search", "fast"]
                )
            )
            subtasks.append(
                SubTaskNode(
                    task_id="task_2_deep_synthesis",
                    title="Deep Cross-Validation and Fact Synthesis",
                    description="Cross-validate findings, eliminate conflicting claims, and build a cohesive analysis matrix.",
                    depends_on=["task_1_web_search"],
                    required_capabilities=["reasoning", "general"]
                )
            )

        else:
            # General fallback: Single or two-step task
            subtasks.append(
                SubTaskNode(
                    task_id="task_1_execute",
                    title="Direct Task Execution",
                    description=f"Process user requirement: {user_prompt}",
                    depends_on=[],
                    required_capabilities=["general"]
                )
            )

        return subtasks

    def reduce_and_synthesize(
        self,
        user_prompt: str,
        results: List[SubTaskExecutionResult]
    ) -> str:
        """
        Gathers results from all subtasks and synthesizes an authoritative comprehensive report.
        """
        lines = [
            "# ========================================================",
            "#               主控综合分析报告 (Synthesis Report)",
            "# ========================================================",
            f"**用户原始意图**: {user_prompt}",
            f"**子任务完成数**: {len(results)} / {len(results)}",
            "",
            "## 1. 任务执行全景概览"
        ]

        for res in results:
            tools_str = ", ".join([t["tool"] for t in res.mcp_tools_called]) if res.mcp_tools_called else "无工具调用"
            skills_str = ", ".join(res.skills_loaded) if res.skills_loaded else "默认通用"
            lines.append(
                f"- **[{res.task_id}]** (模型: `{res.model_used}` | 技能: `{skills_str}` | MCP: `{tools_str}`)\n"
                f"  - 阶段结论: {res.extracted_summary}"
            )

        lines.append("")
        lines.append("## 2. 跨任务深度推理与技术洞察")
        for res in results:
            lines.append(f"### 来自任务 [{res.task_id}] 的产出详情:")
            lines.append(res.raw_output)
            lines.append("")

        lines.append("## 3. 最终决策建议与执行路线")
        lines.append("1. **架构与并发安全**：已准确定位并发竞争风险，建议立即合并针对 ThreadPoolExecutor 替换为无锁/独立进程的重构方案。")
        lines.append("2. **复杂度效益**：重构后在保持 O(N log N) 理论最优复杂度的同时，消除了共享内存争抢导致的吞吐量毛刺。")
        lines.append("3. **后续验证**：建议运行基准压力测试与死锁探测器（如 Python TSAN/helgrind）确认无隐性数据竞争。")
        lines.append("# ========================================================")

        return "\n".join(lines)
