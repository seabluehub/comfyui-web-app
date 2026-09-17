# 本地动漫角色生图系统 (ComfyUI Web App) —— 使用说明手册

> **版本**：v1.0.0  
> **适用环境**：Windows 10/11 (已在 RTX 5090 Laptop 环境充分评估与验证)  
> **依赖环境**：Python 3.10+ (推荐 3.10 ~ 3.13)，可选 ComfyUI 本地实例 (端口 8188)

---

## 一、系统简介

本项目是一套**专为动漫二次元角色工业化量产**设计的纯本地 Web 应用与批处理调度系统：
- **固定角色一致性**：锁定专属角色（默认配置银发紫瞳双马尾美少女 Lumina）核心五官特征；
- **1000 变体参数矩阵**：10 种动漫画风 × 20 套服饰 × 5 种姿态镜头，自动展开并生成 1000 组确定性随机 Seed 与中英文 Prompt；
- **双模灵活驱动**：
  - **Live 真实生产模式**：直连本地 ComfyUI API（默认 `127.0.0.1:8188`），驱动 SDXL / Flux 大模型输出高清图；
  - **Dev 仿真开发模式**：无需 GPU 即可调试全套任务调度、WebSocket 实时步数推送与画廊交互；
- **笔记本物理保护机制**：内置每 30 张自动休眠 15 秒（降温防掉速）与每 50 张调用 ComfyUI `POST /free` 清理 PyTorch 显存碎片；
- **现代化画廊展示**：响应式瀑布流、多维标签筛选、完整 Prompt/Seed 元数据查看与一键复制、一键原图下载。

---

## 二、快速开始（本地部署四步法）

### 第 1 步：解压与进入目录
将下载的 `comfyui-web-app.zip` 解压至本地任意路径（建议全英文路径，如 `D:\comfyui-web-app` 或 `C:\MyAI\comfyui-web-app`）：
```powershell
cd C:\MyAI\comfyui-web-app
```

### 第 2 步：安装 Python 依赖
确保本机已安装 Python 3.10 或更高版本（或使用便携包中自带的 python）：
```powershell
# 推荐使用清华镜像极速安装
python -m pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

### 第 3 步：检查与配置环境变量 (`.env`)
项目根目录下已自带 `.env` 文件，用文本编辑器打开可按需调整：
```ini
# Web 服务端口（若 8080 被占用可改为 8090 等）
PORT=8080
HOST=0.0.0.0

# 是否启用开发仿真模式：
# - 首次体验或无显卡时设为 true；
# - 连接本地真实 ComfyUI 时设为 false！
MOCK_MODE=false

# ComfyUI 服务地址（确保 ComfyUI 已启动在对应端口）
COMFYUI_HOST=127.0.0.1
COMFYUI_PORT=8188

# 笔记本温控与显存参数
COOLDOWN_BATCH_SIZE=30      # 连续完成 30 张休眠
COOLDOWN_SECONDS=15         # 每次休眠 15 秒
FREE_MEMORY_BATCH_SIZE=50   # 连续完成 50 张调用 /free 释放显存
```

### 第 4 步：启动系统

#### 方式 A：启动 Web 交互画廊（推荐）
双击运行根目录下的 **`start_server.bat`**  
或在 PowerShell 中执行：
```powershell
.\start_server.ps1
```
启动成功后，在浏览器访问：👉 **`http://127.0.0.1:8080`**

#### 方式 B：无头命令行批量生成（自动化量产）
若不需要启动浏览器界面，直接在终端执行：
```powershell
# 批量生产前 20 张
python run_batch.py --limit 20

# 生产全部 1000 张（支持断点续跑，随时可 Ctrl+C 中断与恢复）
python run_batch.py

# 重新初始化/重置 1000 变体矩阵
python run_batch.py --force-matrix
```

---

## 三、Web 界面功能使用指南

1. **实时进度看板（顶部 Banner）**：
   - 实时显示 1000 张批量进度百分比、待生成数、已完成数与单张平均耗时；
   - 动态采样步数提示：显示当前正在采样的任务编号、风格标签与步骤百分比（如 `18/25`）；
   - 温控休眠提醒：达到 30 张时自动提示降温倒计时。
2. **生产控制胶囊**：
   - 点击 **【开始量产】**：后台守护进程自动按队列执行任务；
   - 点击 **【暂停】**：正在执行的单张完成后挂起，不丢失进度；再次点击即可无缝恢复；
   - 点击 **【🔄 刷新】**：即时重新同步画廊与数据库状态。
3. **多维标签筛选与检索**：
   - **画风筛选**：点击标签一键过滤（全部、吉卜力、新海诚、赛博朋克、水彩、洛可可、哥特、90s复古等）；
   - **服装筛选**：下拉选择指定服饰（水手服、和服、机能服、风衣、女仆装等）；
   - **姿态与镜头**：筛选动态张力、近景特写、广角风景、闲坐憩息等；
   - **全局搜索**：输入提示词关键词或图片文件名即时匹配。
4. **图片卡片与详情弹窗（Lightbox）**：
   - 悬停卡片：展示种子号（Seed）、提示词摘要，点击 **【📋 复制】** 快捷复制正面 Prompt；
   - 点击卡片：弹出高清大图查看器，展示分辨率、文件大小、LoRA 名称、CFG 与完整中英文提示词，支持一键下载原图。

---

## 四、真实 ComfyUI 连接配置指南

当您在带有 NVIDIA RTX 显卡的笔记本上运行时：

1. **启动 ComfyUI**：
   确保 ComfyUI 正确启动在 `http://127.0.0.1:8188`，并挂载好模型库；
2. **切换模式**：
   将 `.env` 文件中的 `MOCK_MODE=true` 改为：
   ```ini
   MOCK_MODE=false
   ```
3. **配置工作流模板**：
   - 默认工作流位于 `workflows/sdxl_anime_template.json`（SDXL 极速量产方案）；
   - 如使用 Flux，可在 `app/comfy_client.py` 中将模板指定为 `flux_anime_template.json`；
   - 确保模型文件名与您本地 `models/checkpoints/` 及 `models/loras/` 下的文件名一致。

---

## 五、常见问题与排查 (FAQ)

| 现象 | 可能原因 | 解决办法 |
|---|---|---|
| 启动提示 `Address already in use` | 8080 端口被其他软件占用 | 在 `.env` 中将 `PORT=8080` 修改为 `PORT=8090` 或 `8190` 后重启。 |
| Web 界面显示 `ComfyUI未连接` | ComfyUI 进程未启动或端口不正确 | 确认 ComfyUI 运行在 `127.0.0.1:8188`，或在测试阶段保持 `MOCK_MODE=true`。 |
| 批量出图过程中机器发热严重 | 笔记本连续高负荷运行 | 检查 `.env` 中的 `COOLDOWN_BATCH_SIZE=30` 和 `COOLDOWN_SECONDS=15` 是否生效，可调大休眠秒数。 |
| 意外断电/关闭后如何继续 | 任务中断在途中 | 系统在启动时会自动恢复断点，重新运行 `start_server` 或 `run_batch.py` 即可继续从未完成的任务往下出图。 |
