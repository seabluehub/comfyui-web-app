"""
Comprehensive test suite for AI Model, Skill, and MCP Router Adapter.
"""
import pytest
import asyncio
from ai_router_adapter.registry import ModelRegistry, SkillRegistry, MCPRegistry
from ai_router_adapter.schemas import SubTaskNode
from ai_router_adapter.core import Router, ContextAssembler, Supervisor, SubTaskExecutor
from ai_router_adapter.pipeline import AIRouterPipeline


def test_registries_initialization():
    """Verify default models, skills, and MCP tools are registered properly."""
    model_reg = ModelRegistry()
    skill_reg = SkillRegistry()
    mcp_reg = MCPRegistry()

    assert model_reg.get("deepseek-r1") is not None
    assert model_reg.get("claude-3-7-sonnet") is not None
    assert model_reg.get("gemini-2.5-flash") is not None

    assert skill_reg.get("skill_code_audit") is not None
    assert skill_reg.get("skill_algorithm_reasoning") is not None

    tools = mcp_reg.list_all_tools()
    tool_names = [t.tool_name for t in tools]
    assert "get_pull_request" in tool_names
    assert "duckduckgo_search" in tool_names


def test_dynamic_router_model_matching():
    """Verify that tasks route to appropriate models according to requirements."""
    model_reg = ModelRegistry()
    skill_reg = SkillRegistry()
    mcp_reg = MCPRegistry()
    router = Router(model_reg, skill_reg, mcp_reg)

    # 1. Reasoning task -> deepseek-r1
    task_math = SubTaskNode(
        task_id="t1",
        title="Complexity Deduction",
        description="Prove asymptotic time complexity bound O(N log k) and verify absence of deadlock.",
        required_capabilities=["reasoning"]
    )
    decision1 = router.route_subtask(task_math)
    assert decision1.selected_model == "deepseek-r1"
    assert "skill_algorithm_reasoning" in decision1.selected_skills

    # 2. Coding refactor task -> claude-3-7-sonnet
    task_code = SubTaskNode(
        task_id="t2",
        title="Refactor Concurrent Sorter",
        description="Implement defensive code refactor and eliminate bug in sorting implementation.",
        required_capabilities=["coding"]
    )
    decision2 = router.route_subtask(task_code)
    assert decision2.selected_model == "claude-3-7-sonnet"
    assert "skill_code_audit" in decision2.selected_skills

    # 3. Fast extraction task -> gemini-2.5-flash
    task_search = SubTaskNode(
        task_id="t3",
        title="Web Search",
        description="Quickly search and fetch web articles on latest framework release.",
        required_capabilities=["search"]
    )
    decision3 = router.route_subtask(task_search)
    assert decision3.selected_model == "gemini-2.5-flash"


def test_dynamic_router_mcp_whitelist_filtering():
    """Verify that MCP tools are strictly whitelisted to prevent context explosion."""
    model_reg = ModelRegistry()
    skill_reg = SkillRegistry()
    mcp_reg = MCPRegistry()
    router = Router(model_reg, skill_reg, mcp_reg)

    # Task requiring GitHub PR tool
    task_pr = SubTaskNode(
        task_id="t_pr",
        title="Pull Request Inspection",
        description="Inspect pull request and commit diff on GitHub repo.",
        required_capabilities=["search"]
    )
    decision = router.route_subtask(task_pr)

    assert "github_mcp:get_pull_request" in decision.selected_mcp_tools
    # Ensure unrelated tools (like database SQL) are NOT in the whitelist
    assert "database_mcp:execute_sql_query" not in decision.selected_mcp_tools


def test_context_assembler_structure():
    """Verify that context assembler injects skills, dependencies, and tool schemas."""
    skill_reg = SkillRegistry()
    mcp_reg = MCPRegistry()
    assembler = ContextAssembler(skill_reg, mcp_reg)

    task = SubTaskNode(
        task_id="task_2",
        title="Audit Code Diff",
        description="Audit the patch for race hazards.",
        depends_on=["task_1"],
        required_capabilities=["reasoning"]
    )

    from ai_router_adapter.schemas import RouteDecision, SubTaskExecutionResult
    decision = RouteDecision(
        task_id="task_2",
        selected_model="deepseek-r1",
        model_reason="High reasoning capability",
        selected_skills=["skill_code_audit"],
        selected_mcp_tools=["github_mcp:get_pull_request"],
        routing_summary="summary"
    )

    upstream = {
        "task_1": SubTaskExecutionResult(
            task_id="task_1",
            status="success",
            model_used="gemini-2.5-flash",
            skills_loaded=[],
            mcp_tools_called=[],
            extracted_summary="PR diff has 45 lines changed in sort.py.",
            raw_output="Raw diff"
        )
    }

    assembled = assembler.assemble(task, decision, upstream)

    # Verify skill injected into system prompt
    assert "Code Architecture & Security Audit" in assembled.system_prompt
    # Verify upstream dependency injected into user prompt
    assert "PR diff has 45 lines changed in sort.py" in assembled.user_prompt
    # Verify tool schema is present and properly formatted
    assert len(assembled.available_tools) == 1
    assert assembled.available_tools[0]["function"]["name"] == "github_mcp:get_pull_request"


def test_end_to_end_pipeline_code_audit():
    """Verify full end-to-end multi-agent pipeline on a code audit prompt."""
    pipeline = AIRouterPipeline(use_mock=True)

    prompt = "请帮我审查 GitHub PR #308 中的高性能排序算法，分析其时间空间复杂度并检查是否存在并发死锁漏洞"
    output = asyncio.run(pipeline.run(prompt))

    # 1. Verification of Supervisor Plan
    assert len(output.subtasks) == 3
    task_ids = [t.task_id for t in output.subtasks]
    assert "task_1_fetch_context" in task_ids
    assert "task_2_reasoning_audit" in task_ids
    assert "task_3_code_refactor" in task_ids

    # 2. Verification of Routing Decisions
    assert output.routing_decisions["task_1_fetch_context"].selected_model == "gemini-2.5-flash"
    assert "github_mcp:get_pull_request" in output.routing_decisions["task_1_fetch_context"].selected_mcp_tools

    assert output.routing_decisions["task_2_reasoning_audit"].selected_model == "deepseek-r1"
    assert "skill_algorithm_reasoning" in output.routing_decisions["task_2_reasoning_audit"].selected_skills

    assert output.routing_decisions["task_3_code_refactor"].selected_model == "claude-3-7-sonnet"
    assert "skill_code_audit" in output.routing_decisions["task_3_code_refactor"].selected_skills

    # 3. Verification of SubTask Execution Results
    assert len(output.subtask_results) == 3
    for res in output.subtask_results:
        assert res.status == "success"
        assert len(res.extracted_summary) > 0

    # 4. Verification of Supervisor Final Synthesis
    assert "主控综合分析报告" in output.final_synthesis
    assert "task_1_fetch_context" in output.final_synthesis
    assert "task_2_reasoning_audit" in output.final_synthesis
    assert "task_3_code_refactor" in output.final_synthesis
    assert "最终决策建议与执行路线" in output.final_synthesis


def test_end_to_end_pipeline_research():
    """Verify end-to-end pipeline on an industry research prompt."""
    pipeline = AIRouterPipeline(use_mock=True)

    prompt = "调研 Python 3.13 free-threaded 无 GIL 模式下的并发性能基准与最新发展趋势"
    output = asyncio.run(pipeline.run(prompt))

    assert len(output.subtasks) == 2
    assert output.subtasks[0].task_id == "task_1_web_search"
    assert output.routing_decisions["task_1_web_search"].selected_model == "gemini-2.5-flash"
    assert "web_search_mcp:duckduckgo_search" in output.routing_decisions["task_1_web_search"].selected_mcp_tools
    assert len(output.subtask_results) == 2
    assert "主控综合分析报告" in output.final_synthesis

