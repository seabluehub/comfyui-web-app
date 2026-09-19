"""
Demo Script: Interactive demonstration of the AI Router Adapter.
Run with: C:\\Python31011\\python.exe ai_router_adapter/demo.py
"""
import asyncio
import sys
import os

# Set UTF-8 for console output on Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

# Ensure package root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from ai_router_adapter.pipeline import AIRouterPipeline
from ai_router_adapter.schemas import SubTaskNode, RouteDecision, AssembledContext, SubTaskExecutionResult


# ANSI color codes for rich terminal display
CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
MAGENTA = "\033[95m"
BLUE = "\033[94m"
BOLD = "\033[1m"
RESET = "\033[0m"


def print_step(step_name: str, data: any):
    if step_name == "plan_start":
        print(f"\n{BOLD}{CYAN}======================================================================{RESET}")
        print(f"{BOLD}{CYAN} [1. 主控规划器 Supervisor Plan & Decompose] {RESET}")
        print(f"{BOLD}用户原始需求:{RESET} {data}\n")

    elif step_name == "plan_done":
        subtasks = data
        print(f"{GREEN}[OK] 任务拆解完成，共编排 {len(subtasks)} 个协同子任务 (DAG):{RESET}")
        for i, t in enumerate(subtasks, 1):
            deps = f"(依赖: {', '.join(t.depends_on)})" if t.depends_on else "(无依赖，可立即执行)"
            print(f"  {BOLD}{i}. [{t.task_id}]{RESET} - {t.title} {YELLOW}{deps}{RESET}")
            print(f"     详情: {t.description}")
            print(f"     需求特征: {t.required_capabilities}")

    elif step_name == "route_decision":
        decision: RouteDecision = data
        print(f"\n{BOLD}{MAGENTA}----------------------------------------------------------------------{RESET}")
        print(f"{BOLD}{MAGENTA} [2. 动态路由匹配器 Route Decision for: {decision.task_id}] {RESET}")
        print(f"  [MODEL] {BOLD}选定大模型:{RESET} {CYAN}{decision.selected_model}{RESET} ({decision.model_reason})")
        skills_str = ", ".join(decision.selected_skills) if decision.selected_skills else "无（使用通用基底）"
        print(f"  [SKILL] {BOLD}加载技能库 (Skills):{RESET} {YELLOW}{skills_str}{RESET}")
        tools_str = ", ".join(decision.selected_mcp_tools) if decision.selected_mcp_tools else "无（无需外部工具）"
        print(f"  [MCP]   {BOLD}下发 MCP 工具白名单:{RESET} {GREEN}{tools_str}{RESET}")

    elif step_name == "context_assembled":
        ctx: AssembledContext = data
        print(f"\n{BLUE}  [Context 封装预览]{RESET}")
        tool_count = len(ctx.available_tools)
        print(f"  - 挂载工具数: {tool_count} 个 (严格白名单限制，杜绝上下文爆炸与注意力涣散)")
        print(f"  - System Prompt 长度: {len(ctx.system_prompt)} 字符 (已动态注入领域技能指令)")
        print(f"  - User Prompt 长度: {len(ctx.user_prompt)} 字符 (已挂载前置依赖结果)")

    elif step_name == "subtask_finished":
        res: SubTaskExecutionResult = data
        print(f"\n{GREEN}  [SUCCESS: 子任务执行完成 {res.task_id}]{RESET}")
        if res.mcp_tools_called:
            print(f"  - 触发 MCP 工具调用: {[t['tool'] for t in res.mcp_tools_called]}")
        print(f"  - 提取结论概要: {res.extracted_summary}")

    elif step_name == "synthesis_start":
        print(f"\n{BOLD}{CYAN}======================================================================{RESET}")
        print(f"{BOLD}{CYAN} [3. 主控全局归约与交叉推理 Supervisor Synthesis] {RESET}\n")


async def main():
    pipeline = AIRouterPipeline(use_mock=True)

    default_prompt = (
        "请帮我审查 GitHub PR #308 中的高性能排序算法，分析其时间空间复杂度并检查是否存在并发死锁漏洞"
    )

    prompt = sys.argv[1] if len(sys.argv) > 1 else default_prompt
    output = await pipeline.run(prompt, on_step_callback=print_step)

    print(output.final_synthesis)
    print(f"\n{BOLD}{GREEN}[ALL COMPLETE] 流程全部成功执行，各模型、Skill、MCP 协同运作完毕！{RESET}\n")



if __name__ == "__main__":
    asyncio.run(main())
