# AI 大模型路由适配器 (AI Multi-Model, Skill & MCP Router Adapter)

> 一套支持**主控任务拆解 (DAG)**、**多维智能路由 (大模型/技能库/MCP工具池)**、**上下文按需封装 (防Token爆炸)** 与 **主控归约综合推理** 的多智能体编排框架。

---

## 快速上手与本地运行验证

本项目支持 Windows 10/11 及 Linux/macOS，仅需 Python 3.10 或更高版本。

### 第一步：解压与进入目录
解压压缩包后，在终端（PowerShell 或 CMD）中进入解压后的根目录：
```powershell
cd ai_router_adapter_package
```

### 第二步：安装运行依赖
推荐创建虚拟环境或使用当前 Python 环境安装依赖（纯标准依赖，极速安装）：
```powershell
# 1. (推荐) 创建并激活虚拟环境
python -m venv .venv
.\.venv\Scripts\Activate.ps1   # CMD 用户请执行: .\.venv\Scripts\activate.bat

# 2. 安装必要依赖（清华镜像加速）
python -m pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

### 第三步：一键运行验证

#### 1. 运行全套自动化测试（6大核心用例）
* **方式 A (Windows 脚本)**：双击 `run_tests.bat`
* **方式 B (命令行)**：
```powershell
python -m pytest ai_router_adapter/tests/test_router_pipeline.py -v
```
**预期测试覆盖项**：
- `test_registries_initialization`：大模型、Skill技能、MCP工具元数据注册正常
- `test_dynamic_router_model_matching`：推理/代码/检索模型加权匹配准确度
- `test_dynamic_router_mcp_whitelist_filtering`：MCP工具严格白名单过滤（防止全量注入导致上下文爆炸）
- `test_context_assembler_structure`：Prompt/Skill/Tool Schemas/上游依赖上下文组装
- `test_end_to_end_pipeline_code_audit`：端到端复杂代码审计与重构任务全流程
- `test_end_to_end_pipeline_research`：端到端行业深度调研多任务编排全流程

#### 2. 运行彩色终端交互演示（Demo）
* **方式 A (Windows 脚本)**：双击 `run_demo.bat`
* **方式 B (命令行自定义 Prompt)**：
```powershell
# 运行默认场景（GitHub PR 审查 + 复杂度推导 + 并发代码重构）
python ai_router_adapter/demo.py

# 或者输入自定义提示词
python ai_router_adapter/demo.py "调研 Python 3.13 free-threaded 无 GIL 模式下的并发性能基准与最新发展趋势"
```

---

## 目录结构说明

```
ai_router_adapter_package/
├── README.md                           # 本说明文档
├── requirements.txt                    # 依赖清单 (pydantic, pytest, anyio)
├── run_tests.bat                       # Windows 一键测试脚本
├── run_demo.bat                        # Windows 一键演示脚本
└── ai_router_adapter/                  # 适配器核心源码包
    ├── __init__.py
    ├── schemas.py                      # 统一数据结构定义 (Task, Model, Skill, MCP)
    ├── pipeline.py                     # 统一编排流水线 (AIRouterPipeline)
    ├── demo.py                         # 控制台彩色演示脚本
    ├── registry/                       # 资源注册中心
    │   ├── model_registry.py           # 模型能力画像 (DeepSeek R1/Claude/Gemini/GPT-4o)
    │   ├── skill_registry.py           # 技能库 (代码审计/算法推理/深度调研/总结)
    │   └── mcp_registry.py             # MCP 服务池 (GitHub/Search/Database 工具与模拟执行)
    ├── core/                           # 核心调度逻辑
    │   ├── supervisor.py               # 主控规划 (Plan DAG) 与 归约总结 (Reduce)
    │   ├── router.py                   # 三维动态路由引擎 (模型/Skill/MCP精准匹配)
    │   ├── context_assembler.py        # 上下文隔离组装器 (防Token爆炸)
    │   └── executor.py                 # Sub-Agent 驱动器与 MCP Tool Calling 循环
    └── tests/                          # 自动化测试套件
        └── test_router_pipeline.py
```

---

## 核心设计要点与实战优势

1. **解决 Token 爆炸与注意力分散**：
   - 绝大多数 Agent 框架的弊端是把所有已接入的 MCP 工具一次性塞进提示词，导致大模型注意力涣散且消耗巨量 Token。
   - 本方案采用**需求特征打分 + 精准白名单机制**，每个 Sub-Agent 每次仅获得 1~3 个最相关的工具定义。
2. **多模型特质互补**：
   - 数据检索与高吞吐提取 ➔ 分流至低成本极速模型（如 `gemini-2.5-flash`）；
   - 算法推演与严密逻辑证明 ➔ 分流至深度推理模型（如 `deepseek-r1`）；
   - 复杂架构重构与代码生成 ➔ 分流至顶级代码模型（如 `claude-3-7-sonnet`）。
3. **主控上下文隔离与产出投影**：
   - 子任务执行中的海量 Raw JSON 与中间 Tool 调用过程保留在子 Agent 内部；
   - 仅将萃取提炼出的精简产出向上传递给主控 Reducer，保障主控长文本逻辑严谨且不爆上下文。
