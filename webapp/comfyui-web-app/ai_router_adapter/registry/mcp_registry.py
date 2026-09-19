"""
MCP Registry: Catalogs MCP Servers, Tools schemas, and execution handlers.
"""
from typing import Dict, List, Optional, Any, Callable
from ..schemas import MCPServerSpec, MCPToolSpec


class MCPRegistry:
    """Registry managing available Model Context Protocol (MCP) servers and tools."""

    def __init__(self):
        self._servers: Dict[str, MCPServerSpec] = {}
        self._tool_handlers: Dict[str, Callable[[Dict[str, Any]], Dict[str, Any]]] = {}
        self._register_default_servers()

    def _register_default_servers(self):
        # 1. GitHub MCP Server
        github_server = MCPServerSpec(
            server_name="github_mcp",
            description="GitHub integration server for repository inspection, pull requests, and commit diffs.",
            tools=[
                MCPToolSpec(
                    tool_name="get_pull_request",
                    server_name="github_mcp",
                    description="Retrieve details, description, changed files, and patch diff of a GitHub PR.",
                    parameters={
                        "type": "object",
                        "properties": {
                            "repo": {"type": "string", "description": "Repository in owner/name format"},
                            "pr_number": {"type": "integer", "description": "PR number"}
                        },
                        "required": ["repo", "pr_number"]
                    }
                ),
                MCPToolSpec(
                    tool_name="search_code",
                    server_name="github_mcp",
                    description="Search for symbols, function definitions, or files across the repository.",
                    parameters={
                        "type": "object",
                        "properties": {
                            "repo": {"type": "string", "description": "Repository in owner/name format"},
                            "query": {"type": "string", "description": "Search keyword or symbol"}
                        },
                        "required": ["repo", "query"]
                    }
                )
            ]
        )
        self.register_server(github_server)

        # 2. Web Search MCP Server
        search_server = MCPServerSpec(
            server_name="web_search_mcp",
            description="Live web search and real-time page content fetcher.",
            tools=[
                MCPToolSpec(
                    tool_name="duckduckgo_search",
                    server_name="web_search_mcp",
                    description="Execute web search and return top snippet results.",
                    parameters={
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "Web search query"}
                        },
                        "required": ["query"]
                    }
                ),
                MCPToolSpec(
                    tool_name="fetch_web_content",
                    server_name="web_search_mcp",
                    description="Fetch and extract readable text from a specified URL.",
                    parameters={
                        "type": "object",
                        "properties": {
                            "url": {"type": "string", "description": "Target webpage URL"}
                        },
                        "required": ["url"]
                    }
                )
            ]
        )
        self.register_server(search_server)

        # 3. Database MCP Server
        db_server = MCPServerSpec(
            server_name="database_mcp",
            description="Relational database inspector and query runner.",
            tools=[
                MCPToolSpec(
                    tool_name="execute_sql_query",
                    server_name="database_mcp",
                    description="Safely execute read-only SQL queries on the database.",
                    parameters={
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "SQL statement"}
                        },
                        "required": ["query"]
                    }
                )
            ]
        )
        self.register_server(db_server)

        # Register default tool mock handlers for testing/demo
        self._register_default_handlers()

    def _register_default_handlers(self):
        def _mock_get_pr(args: Dict[str, Any]) -> Dict[str, Any]:
            pr_num = args.get("pr_number", 100)
            return {
                "pr_number": pr_num,
                "title": "feat: Optimize ParallelMergeSort with multi-threaded chunking",
                "author": "dev-lead",
                "diff_summary": "Modified algorithms/sort.py (+45, -12). Added ThreadPoolExecutor chunk sorting.",
                "code_snippet": (
                    "def parallel_merge_sort(arr, workers=4):\n"
                    "    if len(arr) <= 1024:\n"
                    "        return sorted(arr)\n"
                    "    chunk_size = len(arr) // workers\n"
                    "    # Potential lock contention if shared buffer isn't guarded\n"
                    "    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as ex:\n"
                    "        futures = [ex.submit(sorted, arr[i:i+chunk_size]) for i in range(0, len(arr), chunk_size)]\n"
                    "        chunks = [f.result() for f in futures]\n"
                    "    return merge_chunks(chunks)"
                )
            }

        def _mock_search(args: Dict[str, Any]) -> Dict[str, Any]:
            query = args.get("query", "")
            return {
                "query": query,
                "results": [
                    {
                        "title": f"Recent Technical Developments regarding '{query}'",
                        "snippet": f"Benchmarking shows modern multi-threading in Python 3.13 free-threaded mode vs multiprocessing...",
                        "url": "https://tech-insights.example.com/2026/08/benchmarks"
                    }
                ]
            }

        self.register_handler("github_mcp:get_pull_request", _mock_get_pr)
        self.register_handler("web_search_mcp:duckduckgo_search", _mock_search)

    def register_server(self, server: MCPServerSpec):
        self._servers[server.server_name] = server

    def register_handler(self, tool_key: str, handler: Callable[[Dict[str, Any]], Dict[str, Any]]):
        """tool_key format: server_name:tool_name"""
        self._tool_handlers[tool_key] = handler

    def get_tool(self, server_name: str, tool_name: str) -> Optional[MCPToolSpec]:
        server = self._servers.get(server_name)
        if not server:
            return None
        for t in server.tools:
            if t.tool_name == tool_name:
                return t
        return None

    def list_all_tools(self) -> List[MCPToolSpec]:
        tools = []
        for s in self._servers.values():
            tools.extend(s.tools)
        return tools

    def list_all_servers(self) -> List[MCPServerSpec]:
        return list(self._servers.values())

    def execute_tool(self, server_name: str, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        key = f"{server_name}:{tool_name}"
        handler = self._tool_handlers.get(key)
        if handler:
            return handler(arguments)
        return {"status": "success", "result": f"Executed {key} with {arguments}"}
